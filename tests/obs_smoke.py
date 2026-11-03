"""Real libobs/D3D11 integration test, isolated from the user's running OBS.

Requires Python 3.12+ and the installed OBS runtime. Never reads OBS profiles,
scenes, credentials, capture devices, or the frontend's websocket server.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import threading
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
OBS = Path(os.environ.get("OBS_DIR", r"C:\Program Files\obs-studio"))
OUT = ROOT / "test-output"
OUT.mkdir(exist_ok=True)
DLL_DIR = os.add_dll_directory(str(OBS / "bin/64bit"))
os.chdir(OBS / "bin/64bit")
lib = C.CDLL(str(OBS / "bin/64bit/obs.dll"))
P, S, U, I, B = C.c_void_p, C.c_char_p, C.c_uint32, C.c_int, C.c_bool


def api(name, result, *args):
    fn = getattr(lib, name)
    fn.restype = result
    fn.argtypes = args
    return fn


class VideoInfo(C.Structure):
    _fields_ = [
        ("graphics_module", S), ("fps_num", U), ("fps_den", U),
        ("base_width", U), ("base_height", U), ("output_width", U),
        ("output_height", U), ("output_format", I), ("adapter", U),
        ("gpu_conversion", B), ("colorspace", I), ("range", I),
        ("scale_type", I),
    ]


class VideoData(C.Structure):
    _fields_ = [("data", P * 8), ("linesize", U * 8), ("timestamp", C.c_uint64)]


Callback = C.CFUNCTYPE(None, P, C.POINTER(VideoData))
startup = api("obs_startup", B, S, S, P)
shutdown = api("obs_shutdown", None)
add_data = api("obs_add_data_path", None, S)
reset_video = api("obs_reset_video", I, C.POINTER(VideoInfo))
open_module = api("obs_open_module", I, C.POINTER(P), S, S)
init_module = api("obs_init_module", B, P)
data_create = api("obs_data_create", P)
data_release = api("obs_data_release", None, P)
data_string = api("obs_data_set_string", None, P, S, S)
data_int = api("obs_data_set_int", None, P, S, C.c_int64)
data_double = api("obs_data_set_double", None, P, S, C.c_double)
data_get_double = api("obs_data_get_double", C.c_double, P, S)
create = api("obs_source_create", P, S, S, P, P)
release = api("obs_source_release", None, P)
settings_get = api("obs_source_get_settings", P, P)
source_update = api("obs_source_update", None, P, P)
filter_add = api("obs_source_filter_add", None, P, P)
filter_remove = api("obs_source_filter_remove", None, P, P)
enable = api("obs_source_set_enabled", None, P, B)
output_source = api("obs_set_output_source", None, U, P)
source_properties = api("obs_source_properties", P, P)
destroy_properties = api("obs_properties_destroy", None, P)
first_property = api("obs_properties_first", P, P)
next_property = api("obs_property_next", B, C.POINTER(P))
property_type = api("obs_property_get_type", I, P)
group_content = api("obs_property_group_content", P, P)
get_property = api("obs_properties_get", P, P, S)
click = api("obs_property_button_clicked", B, P, P)
add_callback = api("obs_add_raw_video_callback", None, P, Callback, P)
remove_callback = api("obs_remove_raw_video_callback", None, Callback, P)
average_render = api("obs_get_average_frame_time_ns", C.c_uint64)


def utf8(path):
    return str(path).encode("utf-8")


def load(path, data):
    module = P()
    assert open_module(C.byref(module), utf8(path), utf8(data)) == 0, path
    assert init_module(module), path
    return module


def png(path, width, height, pixels):
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload)))
    raw = b"".join(b"\0" + pixels[y * width * 4:(y + 1) * width * 4]
                   for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def property_count(props):
    count = 0
    p = P(first_property(props))
    while p.value:
        count += 1
        # OBS_PROPERTY_GROUP = 12 in the pinned public OBS headers.
        if property_type(p) == 12:
            count += property_count(group_content(p))
        next_property(C.byref(p))
    return count


condition = threading.Condition()
frames = []


@Callback
def receive(_, frame):
    f = frame.contents
    # Native D3D11 SDR output is BGRA. Convert to RGBA for PNG and assertions.
    pixels = bytearray(b"".join(C.string_at(f.data[0] + y * f.linesize[0], 640 * 4)
                                for y in range(480)))
    red, blue = pixels[0::4], pixels[2::4]
    pixels[0::4], pixels[2::4] = blue, red
    pixels = bytes(pixels)
    with condition:
        frames.append(pixels)
        if len(frames) > 180:
            del frames[0]
        condition.notify_all()


def collect(count):
    deadline = time.monotonic() + 15
    with condition:
        frames.clear()
        while len(frames) < count:
            remaining = deadline - time.monotonic()
            assert remaining > 0, f"Video callback timeout ({len(frames)}/{count})"
            condition.wait(remaining)
        return list(frames)


def main():
    width, height = 640, 480
    bars = [(235, 235, 235), (235, 235, 16), (16, 235, 235),
            (16, 235, 16), (235, 16, 235), (235, 16, 16), (16, 16, 235), (16, 16, 16)]
    pixels = bytes(channel for y in range(height) for x in range(width)
                   for channel in (*bars[x * 8 // width], 255))
    png(OUT / "test-pattern.png", width, height, pixels)
    assert startup(b"en-US", utf8(OUT), None)
    source = effect = props = settings = None
    connected = False
    try:
        add_data(utf8(OBS / "data/libobs"))
        video = VideoInfo(utf8(OBS / "bin/64bit/libobs-d3d11.dll"), 60, 1,
                          width, height, width, height, 7, 0, False, 2, 2, 0)
        assert reset_video(C.byref(video)) == 0, "D3D11 initialization failed"
        load(OBS / "obs-plugins/64bit/image-source.dll", OBS / "data/obs-plugins/image-source")
        load(Path(os.environ.get("NTSC_PLUGIN_DLL", ROOT / "target/release/obs_ntsc_rs.dll")), ROOT)
        image_settings = data_create()
        data_string(image_settings, b"file", utf8(OUT / "test-pattern.png"))
        source = create(b"image_source", b"isolated-test-pattern", image_settings, None)
        data_release(image_settings)
        assert source
        effect = create(b"ntsc_rs_filter", b"isolated-ntsc-test", None, None)
        assert effect
        props = source_properties(effect)
        count = property_count(props)
        assert count >= 60, f"Missing settings: only {count} properties"
        output_source(0, source)
        add_callback(None, receive, None)
        connected = True
        baseline = collect(30)[-1]
        # Catch a swapped R/B channel in the test harness or source upload.
        yellow = baseline[(240 * width + 120) * 4:(240 * width + 120) * 4 + 3]
        assert yellow[0] > 200 and yellow[1] > 200 and yellow[2] < 50, yellow
        png(OUT / "before.png", width, height, baseline)
        filter_add(source, effect)
        filtered = collect(120)
        tail = filtered[-60:]
        changed = sum(a != b for a, b in zip(baseline, tail[-1]))
        unique = len({hashlib.sha256(f).digest() for f in tail})
        assert changed > width * height // 10, f"No visible effect: {changed} changed bytes"
        assert unique >= 10, f"Effect frozen or too slow: {unique} unique frames"
        png(OUT / "after.png", width, height, tail[-1])
        render_ms = average_render() / 1e6
        enable(effect, False)
        bypass = collect(30)[-1]
        assert bypass == baseline, "Disabling the filter did not restore the input"
        enable(effect, True)
        settings = settings_get(effect)
        data_int(settings, b"internal_height", 240)
        source_update(effect, settings)
        resized = collect(45)[-1]
        assert resized != baseline, "Resizing broke processing"
        # Exercise actual OBS property button callbacks, including Unicode paths.
        preset = OUT / f"preset-test-\u00e4-{time.time_ns()}.json"
        data_string(settings, b"export_path", utf8(preset))
        assert click(get_property(props, b"export_preset"), effect)
        assert preset.exists()
        exported = json.loads(preset.read_text())
        assert exported["version"] == 1
        exported["luma_smear"] = 0.123
        preset.write_text(json.dumps(exported), encoding="utf-8")
        data_string(settings, b"preset_path", utf8(preset))
        assert click(get_property(props, b"import_preset"), effect)
        assert abs(data_get_double(settings, b"luma_smear") - 0.123) < 0.00001
        collect(30)
        # Existing files must not be overwritten by the export callback.
        contents = preset.read_bytes()
        assert click(get_property(props, b"export_preset"), effect)
        assert preset.read_bytes() == contents
        report = {
            "result": "PASS", "runtime": api("obs_get_version_string", S)().decode(),
            "properties_including_groups": count, "changed_bytes": changed,
            "unique_effect_frames_in_60_output_frames": unique,
            "average_obs_render_ms": round(render_ms, 3),
            "checks": ["D3D11 module load", "live GPU-CPU-GPU processing",
                       "animated noise", "bypass", "resolution change",
                       "preset import/export callbacks", "Unicode preset path",
                       "export overwrite protection", "clean shutdown"],
        }
        (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
    finally:
        if connected:
            remove_callback(receive, None)
        output_source(0, None)
        if source and effect:
            filter_remove(source, effect)
        if props:
            destroy_properties(props)
        if settings:
            data_release(settings)
        if effect:
            release(effect)
        if source:
            release(source)
        shutdown()


if __name__ == "__main__":
    main()
