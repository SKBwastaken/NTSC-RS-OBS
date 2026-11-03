#include "bridge.h"
#include <util/bmem.h>
#include <graphics/vec4.h>
#include <stdatomic.h>
#include <stdlib.h>

struct filter {
    obs_source_t *source;
    void *engine;
    gs_texrender_t *capture;
    gs_stagesurf_t *stage[2];
    gs_texture_t *output;
    uint32_t width, height;
    unsigned slot;
    bool staged[2], rendered, has_output;
    float elapsed;
    uint64_t frame;
    atomic_int max_height, fps;
};

double bridge_get(obs_data_t *s, const char *key, int kind)
{
    if (kind == 0 || kind == 4) return obs_data_get_bool(s, key) ? 1.0 : 0.0;
    if (kind == 2) return obs_data_get_double(s, key);
    return (double)obs_data_get_int(s, key);
}

void bridge_set(obs_data_t *s, const char *key, int kind, double value, bool defaults)
{
    if (kind == 0 || kind == 4) {
        if (defaults) obs_data_set_default_bool(s, key, value != 0);
        else obs_data_set_bool(s, key, value != 0);
    } else if (kind == 2) {
        if (defaults) obs_data_set_default_double(s, key, value);
        else obs_data_set_double(s, key, value);
    } else {
        if (defaults) obs_data_set_default_int(s, key, (long long)value);
        else obs_data_set_int(s, key, (long long)value);
    }
}

void *bridge_property(obs_properties_t *props, const char *key, const char *label,
                      const char *description, int kind, double min, double max)
{
    obs_property_t *p = NULL;
    obs_properties_t *children = NULL;
    switch (kind) {
    case 0: p = obs_properties_add_bool(props, key, label); break;
    case 1: p = obs_properties_add_int(props, key, label, (int)min, (int)max, 1); break;
    case 2:
        p = obs_properties_add_float_slider(props, key, label, min, max,
                                            (max - min) <= 2 ? 0.001 : 0.01);
        break;
    case 3: p = obs_properties_add_list(props, key, label, OBS_COMBO_TYPE_LIST, OBS_COMBO_FORMAT_INT); break;
    case 4:
        children = obs_properties_create();
        p = obs_properties_add_group(props, key, label, OBS_GROUP_CHECKABLE, children);
        break;
    }
    if (p && description && *description) obs_property_set_long_description(p, description);
    return kind == 4 ? (void *)children : (void *)p;
}

void bridge_option(void *property, const char *label, uint32_t value)
{
    obs_property_list_add_int(property, label, value);
}

void bridge_log(const char *message) { blog(LOG_INFO, "[obs-ntsc-rs] %s", message); }

static void free_graphics(struct filter *f)
{
    gs_texrender_destroy(f->capture);
    gs_stagesurface_destroy(f->stage[0]);
    gs_stagesurface_destroy(f->stage[1]);
    gs_texture_destroy(f->output);
    f->capture = NULL;
    f->stage[0] = f->stage[1] = NULL;
    f->output = NULL;
    f->staged[0] = f->staged[1] = f->has_output = false;
}

static void update(void *data, obs_data_t *settings)
{
    struct filter *f = data;
    int height = (int)obs_data_get_int(settings, "internal_height");
    int fps = (int)obs_data_get_int(settings, "effect_fps");
    atomic_store(&f->max_height, height < 120 ? 120 : height > 1080 ? 1080 : height);
    atomic_store(&f->fps, fps < 1 ? 1 : fps > 60 ? 60 : fps);
    ntsc_engine_update(f->engine, settings);
}

static void *create(obs_data_t *settings, obs_source_t *source)
{
    struct filter *f = bzalloc(sizeof(*f));
    f->source = source;
    f->engine = ntsc_engine_create(settings);
    if (!f->engine) { bfree(f); return NULL; }
    atomic_init(&f->max_height, 480);
    atomic_init(&f->fps, 30);
    update(f, settings);
    f->elapsed = 1.0f;
    return f;
}

static void destroy(void *data)
{
    struct filter *f = data;
    ntsc_engine_destroy(f->engine);
    obs_enter_graphics();
    free_graphics(f);
    obs_leave_graphics();
    bfree(f);
}

static const char *name(void *unused) { UNUSED_PARAMETER(unused); return "ntsc-rs (NTSC / VHS)"; }

static void defaults(obs_data_t *settings)
{
    obs_data_set_default_int(settings, "internal_height", 480);
    obs_data_set_default_int(settings, "effect_fps", 30);
    ntsc_defaults(settings);
}

static bool preset_button(obs_properties_t *props, obs_property_t *p, void *data)
{
    struct filter *f = data;
    if (!f) return false;
    obs_data_t *settings = obs_source_get_settings(f->source);
    bool importing = strcmp(obs_property_name(p), "import_preset") == 0;
    const char *path = obs_data_get_string(settings, importing ? "preset_path" : "export_path");
    bool ok = importing ? ntsc_import(settings, path) : ntsc_export(settings, path);
    if (ok && importing) obs_source_update(f->source, settings);
    obs_property_set_description(obs_properties_get(props, "preset_status"),
                                ok ? "Preset: OK" : "Preset failed. Check the path and OBS log.");
    obs_data_release(settings);
    return true;
}

static obs_properties_t *properties(void *data)
{
    UNUSED_PARAMETER(data);
    obs_properties_t *props = obs_properties_create();
    obs_properties_add_text(props, "info",
        "CPU effect, asynchronous. SDR only. Adds variable video latency; audio is not delayed.",
        OBS_TEXT_INFO);
    obs_properties_add_int(props, "internal_height", "Maximum processing height", 120, 1080, 2);
    obs_properties_add_int(props, "effect_fps", "Maximum effect FPS", 1, 60, 1);
    obs_properties_add_path(props, "preset_path", "ntsc-rs preset (.json)", OBS_PATH_FILE,
                            "ntsc-rs preset (*.json)", NULL);
    obs_properties_add_button(props, "import_preset", "Import preset", preset_button);
    obs_properties_add_path(props, "export_path", "Export preset to (.json)", OBS_PATH_FILE_SAVE,
                            "ntsc-rs preset (*.json)", NULL);
    obs_properties_add_button(props, "export_preset", "Export preset (new file only)", preset_button);
    obs_properties_add_text(props, "preset_status", "Preset: choose a JSON file, then Import.", OBS_TEXT_INFO);
    ntsc_properties(props);
    return props;
}

static void tick(void *data, float seconds)
{
    struct filter *f = data;
    f->rendered = false;
    f->elapsed += seconds;
    if (f->elapsed > 1.0f) f->elapsed = 1.0f;
}

static void draw(struct filter *f, uint32_t width, uint32_t height)
{
    gs_effect_t *effect = obs_get_base_effect(OBS_EFFECT_DEFAULT);
    bool previous = gs_framebuffer_srgb_enabled();
    gs_enable_framebuffer_srgb(true);
    gs_effect_set_texture_srgb(gs_effect_get_param_by_name(effect, "image"), f->output);
    while (gs_effect_loop(effect, "Draw")) gs_draw_sprite(f->output, 0, width, height);
    gs_enable_framebuffer_srgb(previous);
}

static void render(void *data, gs_effect_t *unused)
{
    UNUSED_PARAMETER(unused);
    struct filter *f = data;
    obs_source_t *target = obs_filter_get_target(f->source);
    obs_source_t *parent = obs_filter_get_parent(f->source);
    if (!target || !parent) { obs_source_skip_video_filter(f->source); return; }
    const enum gs_color_space preferred[] = {GS_CS_SRGB};
    if (gs_get_color_space() != GS_CS_SRGB ||
        obs_source_get_color_space(target, 1, preferred) != GS_CS_SRGB) {
        obs_source_skip_video_filter(f->source);
        return;
    }
    uint32_t sw = obs_source_get_base_width(target), sh = obs_source_get_base_height(target);
    if (!sw || !sh) { obs_source_skip_video_filter(f->source); return; }
    uint32_t h = sh < (uint32_t)atomic_load(&f->max_height) ? sh : (uint32_t)atomic_load(&f->max_height);
    uint32_t w = (uint32_t)((uint64_t)sw * h / sh);
    if (w < 2) w = 2;
    /* Bound unusual source aspect ratios as well as vertical resolution. */
    if (w > 1920) { h = (uint32_t)((uint64_t)h * 1920 / w); w = 1920; }
    if (h < 2) h = 2;
    if (w != f->width || h != f->height) {
        free_graphics(f);
        f->width = w; f->height = h; f->slot = 0;
        f->capture = gs_texrender_create(GS_RGBA, GS_ZS_NONE);
        f->stage[0] = gs_stagesurface_create(w, h, GS_RGBA);
        f->stage[1] = gs_stagesurface_create(w, h, GS_RGBA);
        f->output = gs_texture_create(w, h, GS_RGBA, 1, NULL, GS_DYNAMIC);
    }
    if (!f->capture || !f->stage[0] || !f->stage[1] || !f->output) {
        obs_source_skip_video_filter(f->source); return;
    }
    if (!f->rendered) {
        f->rendered = true;
        const uint8_t *result = ntsc_take(f->engine, w, h);
        if (result) { gs_texture_set_image(f->output, result, w * 4, false); f->has_output = true; }
        float interval = 1.0f / atomic_load(&f->fps);
        /* OBS frame durations are rounded to integer nanoseconds. Without a
           small tolerance, 60 -> 30 FPS can accidentally become 20 FPS. */
        if (f->elapsed + 0.000001f >= interval) {
            f->elapsed -= interval;
            if (f->elapsed < 0.0f || f->elapsed > interval) f->elapsed = 0.0f;
            unsigned previous = f->slot ^ 1;
            if (f->staged[previous]) {
                uint8_t *pixels = NULL;
                uint32_t stride = 0;
                if (gs_stagesurface_map(f->stage[previous], &pixels, &stride)) {
                    ntsc_submit(f->engine, pixels, stride, w, h, f->frame++);
                    gs_stagesurface_unmap(f->stage[previous]);
                }
                f->staged[previous] = false;
            }
            gs_texrender_reset(f->capture);
            gs_blend_state_push();
            gs_blend_function(GS_BLEND_ONE, GS_BLEND_ZERO);
            if (gs_texrender_begin(f->capture, w, h)) {
                struct vec4 clear;
                vec4_zero(&clear);
                gs_clear(GS_CLEAR_COLOR, &clear, 0, 0);
                gs_ortho(0, (float)sw, 0, (float)sh, -100, 100);
                uint32_t flags = obs_source_get_output_flags(target);
                if (target == parent && !(flags & OBS_SOURCE_CUSTOM_DRAW) && !(flags & OBS_SOURCE_ASYNC))
                    obs_source_default_render(target);
                else obs_source_video_render(target);
                gs_texrender_end(f->capture);
                gs_stage_texture(f->stage[f->slot], gs_texrender_get_texture(f->capture));
                f->staged[f->slot] = true;
                f->slot ^= 1;
            }
            gs_blend_state_pop();
        }
    }
    if (f->has_output) draw(f, sw, sh);
    else obs_source_skip_video_filter(f->source);
}

bool bridge_load(void)
{
    struct obs_source_info info = {0};
    info.id = "ntsc_rs_filter";
    info.type = OBS_SOURCE_TYPE_FILTER;
    info.output_flags = OBS_SOURCE_VIDEO;
    info.get_name = name;
    info.create = create;
    info.destroy = destroy;
    info.update = update;
    info.get_defaults = defaults;
    info.get_properties = properties;
    info.video_tick = tick;
    info.video_render = render;
    obs_register_source(&info);
    bridge_log("Loaded 0.1.0, native asynchronous NTSC/VHS filter");
    return true;
}

uint32_t bridge_version(void) { return LIBOBS_API_VER; }
