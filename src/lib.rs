//! Rust processing engine, with a small C bridge using the official OBS headers.
#![allow(clippy::missing_safety_doc)]

use ntsc_rs::{
    Context, NtscEffect, YiqView,
    settings::{AnySetting, SettingDescriptor, SettingKind, SettingsList},
    yiq_fielding::{BlitInfo, DeinterlaceMode, Rgbx},
};
use std::{
    ffi::{CStr, CString, c_char, c_void},
    panic::{AssertUnwindSafe, catch_unwind},
    ptr,
    sync::{Arc, Condvar, Mutex, OnceLock},
    thread::{self, JoinHandle},
};

type Handle = *mut c_void;

unsafe extern "C" {
    fn bridge_get(data: Handle, key: *const c_char, kind: i32) -> f64;
    fn bridge_set(data: Handle, key: *const c_char, kind: i32, value: f64, defaults: bool);
    fn bridge_property(
        props: Handle,
        key: *const c_char,
        label: *const c_char,
        description: *const c_char,
        kind: i32,
        min: f64,
        max: f64,
    ) -> Handle;
    fn bridge_option(property: Handle, label: *const c_char, value: u32);
    fn bridge_log(message: *const c_char);
    fn bridge_load() -> bool;
    fn bridge_version() -> u32;
}

fn c(s: &str) -> CString {
    CString::new(s.replace('\0', "")).unwrap()
}

fn log(message: &str) {
    unsafe { bridge_log(c(message).as_ptr()) }
}

fn guarded<T: Default>(f: impl FnOnce() -> T) -> T {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(value) => value,
        Err(_) => {
            log("Operation failed: Rust panic contained at plugin boundary");
            T::default()
        }
    }
}

fn settings_list() -> &'static SettingsList<NtscEffect> {
    static LIST: OnceLock<SettingsList<NtscEffect>> = OnceLock::new();
    LIST.get_or_init(SettingsList::new)
}

fn kind(d: &SettingDescriptor<NtscEffect>) -> (i32, f64, f64) {
    match &d.kind {
        SettingKind::Boolean => (0, 0.0, 1.0),
        SettingKind::IntRange { range } => (1, *range.start() as f64, *range.end() as f64),
        SettingKind::Percentage { .. } => (2, 0.0, 1.0),
        SettingKind::FloatRange { range, .. } => (2, *range.start() as f64, *range.end() as f64),
        SettingKind::Enumeration { .. } => (3, 0.0, 0.0),
        SettingKind::Group { .. } => (4, 0.0, 1.0),
    }
}

fn number(value: AnySetting) -> f64 {
    match value {
        AnySetting::Enum(v) => v as f64,
        AnySetting::Int(v) => v as f64,
        AnySetting::Float(v) => v as f64,
        AnySetting::Bool(v) => {
            if v {
                1.0
            } else {
                0.0
            }
        }
    }
}

/// Clamp numeric settings and reject unknown enum values, including imported JSON.
fn validated(d: &SettingDescriptor<NtscEffect>, value: f64, fallback: AnySetting) -> AnySetting {
    let (k, min, max) = kind(d);
    if !value.is_finite() {
        return fallback;
    }
    match k {
        0 | 4 => AnySetting::Bool(value != 0.0),
        1 => AnySetting::Int(value.clamp(min, max) as i32),
        2 => AnySetting::Float(value.clamp(min, max) as f32),
        _ => {
            if let SettingKind::Enumeration { options } = &d.kind
                && let Some(option) = options.iter().find(|o| o.index as f64 == value)
            {
                return AnySetting::Enum(option.index);
            }
            fallback
        }
    }
}

fn read_settings(data: Handle) -> NtscEffect {
    let mut effect = NtscEffect::default();
    for d in settings_list().all_descriptors() {
        let value = unsafe { bridge_get(data, c(d.id.name).as_ptr(), kind(d).0) };
        let value = validated(d, value, (d.id.get)(&effect));
        let _ = (d.id.set)(&mut effect, value);
    }
    effect
}

fn write_settings(data: Handle, effect: &NtscEffect, defaults: bool) {
    let fallback = NtscEffect::default();
    for d in settings_list().all_descriptors() {
        let value = validated(d, number((d.id.get)(effect)), (d.id.get)(&fallback));
        unsafe {
            bridge_set(
                data,
                c(d.id.name).as_ptr(),
                kind(d).0,
                number(value),
                defaults,
            )
        }
    }
}

fn add_properties(props: Handle, descriptors: &[SettingDescriptor<NtscEffect>]) {
    for d in descriptors {
        let (k, min, max) = kind(d);
        let property = unsafe {
            bridge_property(
                props,
                c(d.id.name).as_ptr(),
                c(d.label).as_ptr(),
                c(d.description.unwrap_or("")).as_ptr(),
                k,
                min,
                max,
            )
        };
        if property.is_null() {
            continue;
        }
        match &d.kind {
            SettingKind::Enumeration { options } => {
                for option in options {
                    unsafe { bridge_option(property, c(option.label).as_ptr(), option.index) }
                }
            }
            SettingKind::Group { children } => add_properties(property, children),
            _ => {}
        }
    }
}

struct Frame {
    pixels: Vec<u8>,
    width: usize,
    height: usize,
    number: usize,
}

struct State {
    effect: NtscEffect,
    revision: u64,
    pending: Option<Frame>,
    output: Option<Frame>,
    stop: bool,
}

struct Engine {
    shared: Arc<(Mutex<State>, Condvar)>,
    display: Mutex<Option<Frame>>,
    worker: Option<JoinHandle<()>>,
}

fn process(ctx: &Context, effect: &NtscEffect, frame: &mut Frame, scratch: &mut Vec<f32>) {
    // OBS textures use premultiplied alpha. ntsc-rs expects straight RGB and
    // overwrites its fourth channel with opaque alpha.
    let alpha: Vec<u8> = frame.pixels.chunks_exact(4).map(|p| p[3]).collect();
    for pixel in frame.pixels.chunks_exact_mut(4) {
        for channel in 0..3 {
            pixel[channel] = if pixel[3] == 0 {
                0
            } else {
                ((pixel[channel] as u32 * 255 / pixel[3] as u32).min(255)) as u8
            };
        }
    }
    let dimensions = (frame.width, frame.height);
    let field = effect.use_field.to_yiq_field(frame.number);
    scratch.resize(YiqView::buf_length_for(dimensions, field), 0.0);
    let mut view = YiqView::from_parts(scratch, dimensions, field);
    let blit = BlitInfo::from_full_frame(frame.width, frame.height, frame.width * 4);
    view.set_from_strided_buffer::<Rgbx, u8, _>(ctx, &frame.pixels, blit, ());
    effect.apply_effect_to_yiq(ctx, &mut view, frame.number, [1.0, 1.0]);
    view.write_to_strided_buffer::<Rgbx, u8, _>(
        ctx,
        &mut frame.pixels,
        blit,
        DeinterlaceMode::Bob,
        (),
    );
    for (pixel, alpha) in frame.pixels.chunks_exact_mut(4).zip(alpha) {
        for channel in pixel.iter_mut().take(3) {
            *channel = ((*channel as u32 * alpha as u32 + 127) / 255) as u8;
        }
        pixel[3] = alpha;
    }
}

impl Engine {
    fn new(effect: NtscEffect) -> std::io::Result<Self> {
        let shared = Arc::new((
            Mutex::new(State {
                effect,
                revision: 0,
                pending: None,
                output: None,
                stop: false,
            }),
            Condvar::new(),
        ));
        let state = shared.clone();
        let worker = thread::Builder::new()
            .name("ntsc-rs-obs".into())
            .stack_size(8 * 1024 * 1024)
            .spawn(move || {
                let result = catch_unwind(AssertUnwindSafe(|| {
                    let ctx = Context::new();
                    let mut scratch = Vec::new();
                    loop {
                        let (mut frame, effect, revision) = {
                            let mut lock = state.0.lock().unwrap();
                            while !lock.stop && lock.pending.is_none() {
                                lock = state.1.wait(lock).unwrap();
                            }
                            if lock.stop {
                                break;
                            }
                            (
                                lock.pending.take().unwrap(),
                                lock.effect.clone(),
                                lock.revision,
                            )
                        };
                        process(&ctx, &effect, &mut frame, &mut scratch);
                        let mut lock = state.0.lock().unwrap();
                        if lock.revision == revision && !lock.stop {
                            lock.output = Some(frame);
                        }
                    }
                }));
                if result.is_err() {
                    log("Processing thread stopped after a contained panic");
                }
                // Context and its Rayon pool are dropped before the module can unload.
            })?;
        Ok(Self {
            shared,
            display: Mutex::new(None),
            worker: Some(worker),
        })
    }

    fn update(&self, effect: NtscEffect) {
        let mut lock = self.shared.0.lock().unwrap();
        lock.effect = effect;
        lock.revision += 1;
        lock.pending = None;
        lock.output = None;
    }

    fn submit(&self, frame: Frame) -> bool {
        let Ok(mut lock) = self.shared.0.try_lock() else {
            return false;
        };
        if lock.stop {
            return false;
        }
        // Latest frame wins. No unbounded queue when processing is slower than OBS.
        lock.pending = Some(frame);
        self.shared.1.notify_one();
        true
    }
}

impl Drop for Engine {
    fn drop(&mut self) {
        {
            let mut lock = self.shared.0.lock().unwrap_or_else(|e| e.into_inner());
            lock.stop = true;
            lock.pending = None;
            self.shared.1.notify_one();
        }
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn obs_module_load() -> bool {
    guarded(|| unsafe { bridge_load() })
}
#[unsafe(no_mangle)]
pub extern "C" fn obs_module_ver() -> u32 {
    unsafe { bridge_version() }
}
#[unsafe(no_mangle)]
pub extern "C" fn obs_module_set_pointer(_module: Handle) {}
#[unsafe(no_mangle)]
pub extern "C" fn obs_module_name() -> *const c_char {
    c"ntsc-rs for OBS".as_ptr()
}
#[unsafe(no_mangle)]
pub extern "C" fn obs_module_description() -> *const c_char {
    c"Native asynchronous NTSC/VHS simulation powered by ntsc-rs".as_ptr()
}

#[unsafe(no_mangle)]
pub extern "C" fn ntsc_engine_create(data: Handle) -> Handle {
    guarded(|| match Engine::new(read_settings(data)) {
        Ok(engine) => Box::into_raw(Box::new(engine)).cast(),
        Err(err) => {
            log(&format!("Could not create worker: {err}"));
            ptr::null_mut()
        }
    })
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn ntsc_engine_destroy(engine: Handle) {
    guarded(|| {
        if !engine.is_null() {
            drop(unsafe { Box::from_raw(engine.cast::<Engine>()) });
        }
    });
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn ntsc_engine_update(engine: Handle, data: Handle) {
    guarded(|| {
        if let Some(engine) = unsafe { engine.cast::<Engine>().as_ref() } {
            engine.update(read_settings(data));
        }
    });
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn ntsc_submit(
    engine: Handle,
    pixels: *const u8,
    stride: u32,
    width: u32,
    height: u32,
    frame: u64,
) -> bool {
    guarded(|| {
        let Some(engine) = (unsafe { engine.cast::<Engine>().as_ref() }) else {
            return false;
        };
        if pixels.is_null()
            || width < 2
            || height < 2
            || width > 1920
            || height > 1080
            || stride < width * 4
        {
            return false;
        }
        let (width, height, stride) = (width as usize, height as usize, stride as usize);
        let mut packed = vec![0u8; width * height * 4];
        for y in 0..height {
            unsafe {
                ptr::copy_nonoverlapping(
                    pixels.add(y * stride),
                    packed.as_mut_ptr().add(y * width * 4),
                    width * 4,
                );
            }
        }
        engine.submit(Frame {
            pixels: packed,
            width,
            height,
            number: frame as usize,
        })
    })
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn ntsc_take(engine: Handle, width: u32, height: u32) -> *const u8 {
    guarded(|| {
        let engine = unsafe { &*engine.cast::<Engine>() };
        let Ok(mut lock) = engine.shared.0.try_lock() else {
            return ptr::null();
        };
        let Some(frame) = lock.output.take() else {
            return ptr::null();
        };
        if frame.width != width as usize || frame.height != height as usize {
            return ptr::null();
        }
        let Ok(mut display) = engine.display.try_lock() else {
            return ptr::null();
        };
        *display = Some(frame);
        display.as_ref().unwrap().pixels.as_ptr()
    })
}

#[unsafe(no_mangle)]
pub extern "C" fn ntsc_defaults(data: Handle) {
    guarded(|| write_settings(data, &NtscEffect::default(), true));
}

#[unsafe(no_mangle)]
pub extern "C" fn ntsc_properties(props: Handle) {
    guarded(|| add_properties(props, &settings_list().setting_descriptors));
}

fn path_string(path: *const c_char) -> Result<String, String> {
    if path.is_null() {
        return Err("No preset path".into());
    }
    let path = unsafe { CStr::from_ptr(path) }
        .to_str()
        .map_err(|e| e.to_string())?;
    if path.is_empty() {
        return Err("Choose a preset file first".into());
    }
    Ok(path.to_owned())
}

fn preset_result(result: Result<(), String>) -> bool {
    match result {
        Ok(()) => true,
        Err(err) => {
            log(&format!("Preset error: {err}"));
            false
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn ntsc_import(data: Handle, path: *const c_char) -> bool {
    guarded(|| {
        preset_result((|| {
            let path = path_string(path)?;
            let metadata = std::fs::metadata(&path).map_err(|e| e.to_string())?;
            if metadata.len() > 1024 * 1024 {
                return Err("Preset exceeds 1 MiB limit".into());
            }
            let json = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
            let effect = settings_list()
                .from_json(&json)
                .map_err(|e| e.to_string())?;
            write_settings(data, &effect, false);
            Ok(())
        })())
    })
}

#[unsafe(no_mangle)]
pub extern "C" fn ntsc_export(data: Handle, path: *const c_char) -> bool {
    guarded(|| {
        preset_result((|| {
            let path = path_string(path)?;
            let json = settings_list()
                .to_json_string(&read_settings(data))
                .map_err(|e| e.to_string())?;
            let mut file = std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(path)
                .map_err(|e| e.to_string())?;
            std::io::Write::write_all(&mut file, json.as_bytes()).map_err(|e| e.to_string())?;
            Ok(())
        })())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{Duration, Instant};

    fn frame(w: usize, h: usize) -> Frame {
        let pixels = (0..w * h)
            .flat_map(|i| {
                [
                    (i % w * 255 / w) as u8,
                    (i / w * 255 / h) as u8,
                    100,
                    (i % 256) as u8,
                ]
            })
            .collect();
        Frame {
            pixels,
            width: w,
            height: h,
            number: 7,
        }
    }

    #[test]
    fn processing_changes_rgb_and_preserves_alpha() {
        let mut frame = frame(64, 48);
        let before = frame.pixels.clone();
        process(
            &Context::new(),
            &NtscEffect::default(),
            &mut frame,
            &mut Vec::new(),
        );
        assert_ne!(frame.pixels, before);
        assert!(
            frame
                .pixels
                .chunks_exact(4)
                .zip(before.chunks_exact(4))
                .all(|(a, b)| a[3] == b[3])
        );
        assert!(
            frame
                .pixels
                .chunks_exact(4)
                .all(|p| p[..3].iter().all(|v| *v <= p[3]))
        );
    }

    #[test]
    fn small_odd_frames_and_all_field_modes() {
        let ctx = Context::new();
        let descriptor = settings_list()
            .all_descriptors()
            .find(|d| d.id.name == "use_field")
            .unwrap();
        let SettingKind::Enumeration { options } = &descriptor.kind else {
            panic!()
        };
        for option in options {
            let mut effect = NtscEffect::default();
            (descriptor.id.set)(&mut effect, AnySetting::Enum(option.index)).unwrap();
            for (w, h) in [(2, 2), (3, 3), (9, 5), (64, 49)] {
                let mut image = frame(w, h);
                process(&ctx, &effect, &mut image, &mut Vec::new());
                assert_eq!(image.pixels.len(), w * h * 4);
            }
        }
    }

    #[test]
    fn preset_roundtrip_and_descriptor_validation() {
        let original = NtscEffect::default();
        let list = settings_list();
        let json = list.to_json_string(&original).unwrap();
        assert_eq!(list.from_json(&json).unwrap(), original);
        assert!(list.from_json("{\"version\":999}").is_err());
        for d in list.all_descriptors() {
            let fallback = (d.id.get)(&original);
            assert_eq!(validated(d, f64::NAN, fallback), fallback);
            assert_eq!(validated(d, number(fallback), fallback), fallback);
        }
    }

    #[test]
    fn worker_returns_a_frame_and_shuts_down() {
        let engine = Engine::new(NtscEffect::default()).unwrap();
        assert!(engine.submit(frame(64, 48)));
        let start = Instant::now();
        loop {
            if let Some(output) = engine.shared.0.lock().unwrap().output.take() {
                assert_eq!(output.pixels.len(), 64 * 48 * 4);
                break;
            }
            assert!(start.elapsed() < Duration::from_secs(10));
            thread::sleep(Duration::from_millis(5));
        }
        engine.update(NtscEffect::default());
        assert!(engine.shared.0.lock().unwrap().output.is_none());
    }
}
