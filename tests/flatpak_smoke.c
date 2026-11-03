/* Test-only native harness. Run inside OBS's actual Flatpak runtime, not --devel.
 * It never starts the frontend, enumerates devices, or loads user configuration.
 * This executable is not shipped in the extension.
 */
#include <obs.h>
#include <obs-nix-platform.h>
#include <util/base.h>
#include <X11/Xlib.h>
#include <errno.h>
#include <glob.h>
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define W 640
#define H 480
#define SIZE (W * H * 4)
#define CHECK(test) do { if (!(test)) { \
    fprintf(stderr, "Flatpak smoke assertion failed at line %d\n", __LINE__); \
    goto done; \
} } while (0)

static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t ready = PTHREAD_COND_INITIALIZER;
static unsigned frames;
static uint8_t last[SIZE], baseline[SIZE], filtered[SIZE];
static uint64_t hashes[60];
static gs_texture_t *texture;
static bool discovered;

static void quiet_log(int level, const char *format, va_list args, void *param)
{
    /* Avoid hardware identifiers and local paths in CI logs. Assertion labels
     * identify failures; use an explicitly private local debug run if needed. */
    (void)level; (void)format; (void)args; (void)param;
}

static const char *pattern_name(void *unused)
{
    (void)unused;
    return "Isolated color bars";
}

static void *pattern_create(obs_data_t *settings, obs_source_t *source)
{
    (void)settings;
    return source;
}

static void pattern_destroy(void *data) { (void)data; }
static uint32_t pattern_width(void *data) { (void)data; return W; }
static uint32_t pattern_height(void *data) { (void)data; return H; }

static void pattern_render(void *data, gs_effect_t *unused)
{
    (void)data; (void)unused;
    gs_effect_t *effect = obs_get_base_effect(OBS_EFFECT_DEFAULT);
    gs_effect_set_texture(gs_effect_get_param_by_name(effect, "image"), texture);
    while (gs_effect_loop(effect, "Draw"))
        gs_draw_sprite(texture, 0, W, H);
}

static void receive(void *param, struct video_data *frame)
{
    (void)param;
    pthread_mutex_lock(&mutex);
    for (unsigned y = 0; y < H; y++)
        memcpy(last + y * W * 4, frame->data[0] + y * frame->linesize[0], W * 4);
    uint64_t hash = UINT64_C(14695981039346656037);
    for (size_t i = 0; i < SIZE; i++)
        hash = (hash ^ last[i]) * UINT64_C(1099511628211);
    hashes[frames % 60] = hash;
    frames++;
    pthread_cond_signal(&ready);
    pthread_mutex_unlock(&mutex);
}

static bool collect(unsigned count, uint8_t *copy, unsigned *unique)
{
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += 30;
    pthread_mutex_lock(&mutex);
    frames = 0;
    memset(hashes, 0, sizeof hashes);
    bool ok = true;
    while (frames < count) {
        if (pthread_cond_timedwait(&ready, &mutex, &deadline) != 0) {
            ok = false;
            break;
        }
    }
    if (copy)
        memcpy(copy, last, SIZE);
    if (unique) {
        *unique = 0;
        for (unsigned i = 0; i < 60; i++) {
            bool seen = false;
            for (unsigned j = 0; j < i; j++)
                seen |= hashes[i] == hashes[j];
            if (!seen && hashes[i])
                (*unique)++;
        }
    }
    pthread_mutex_unlock(&mutex);
    return ok;
}

static void find_plugin(void *param, const struct obs_module_info *info)
{
    (void)param;
    const char *name = strrchr(info->bin_path, '/');
    if (!name || strcmp(name + 1, "obs-ntsc-rs.so"))
        return;
    obs_module_t *module = NULL;
    if (obs_open_module(&module, info->bin_path, info->data_path) == 0)
        discovered = obs_init_module(module);
}

static bool button(obs_properties_t *props, obs_source_t *effect,
                   const char *name, bool expected_success)
{
    obs_property_t *property = obs_properties_get(props, name);
    if (!property || !obs_property_button_clicked(property, effect))
        return false;
    const char *status = obs_property_description(obs_properties_get(props, "preset_status"));
    return expected_success ? strcmp(status, "Preset: OK") == 0
                            : strncmp(status, "Preset failed.", 14) == 0;
}

static bool write_file(const char *path, const char *text)
{
    FILE *file = fopen(path, "wb");
    if (!file)
        return false;
    bool ok = fwrite(text, 1, strlen(text), file) == strlen(text);
    return fclose(file) == 0 && ok;
}

static bool same_file(const char *path, const char *expected)
{
    char buffer[256] = {0};
    FILE *file = fopen(path, "rb");
    if (!file)
        return false;
    size_t size = fread(buffer, 1, sizeof buffer, file);
    bool ok = !ferror(file) && size == strlen(expected) &&
              memcmp(buffer, expected, size) == 0;
    fclose(file);
    return ok;
}

int main(int argc, char **argv)
{
    if (argc != 3 || !getenv("FLATPAK_ID") ||
        strcmp(getenv("FLATPAK_ID"), "com.obsproject.Studio"))
        return 2;
    int result = 1;
    bool started = false, connected = false, attached = false;
    Display *display = NULL;
    obs_source_t *source = NULL, *effect = NULL;
    obs_properties_t *props = NULL;
    obs_data_t *settings = NULL;
    glob_t graphics = {0};
    char preset[4096], denied[4096], report[4096];
    CHECK(snprintf(preset, sizeof preset, "%s/preset-\xc3\xa4.json", argv[1]) < (int)sizeof preset);
    CHECK(snprintf(denied, sizeof denied, "%s/preset.json", argv[2]) < (int)sizeof denied);
    CHECK(snprintf(report, sizeof report, "%s/report.json", argv[1]) < (int)sizeof report);
    CHECK(access(denied, R_OK) != 0);
    CHECK(errno == EACCES || errno == ENOENT);
    CHECK(!write_file("/app/ntsc-rs-test-export.json", "{}"));
    CHECK(access("/.flatpak-info", R_OK) == 0);
    base_set_log_handler(quiet_log, NULL);
    const char *runtime = obs_get_version_string();
    CHECK(atoi(runtime) >= 32);
    CHECK(strspn(runtime, "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.+-_") == strlen(runtime));
    display = XOpenDisplay(NULL);
    CHECK(display);
    obs_set_nix_platform(OBS_NIX_PLATFORM_X11_EGL);
    obs_set_nix_platform_display(display);
    CHECK(obs_startup("en-US", argv[1], NULL));
    started = true;
    obs_add_data_path("/app/share/obs/libobs/");
    CHECK(glob("/app/lib/libobs-opengl.so*", 0, NULL, &graphics) == 0 && graphics.gl_pathc > 0);
    struct obs_video_info video = {
        .graphics_module = graphics.gl_pathv[0],
        .fps_num = 60, .fps_den = 1,
        .base_width = W, .base_height = H, .output_width = W, .output_height = H,
        .output_format = VIDEO_FORMAT_BGRA, .colorspace = VIDEO_CS_709,
        .range = VIDEO_RANGE_FULL, .scale_type = OBS_SCALE_DISABLE,
    };
    CHECK(obs_reset_video(&video) == OBS_VIDEO_SUCCESS);
    obs_add_module_path("/app/plugins/lib/obs-plugins",
                        "/app/plugins/share/obs/obs-plugins/%module%");
    obs_find_modules(find_plugin, NULL);
    CHECK(discovered);
    static const uint8_t colors[8][3] = {
        {235,235,235}, {235,235,16}, {16,235,235}, {16,235,16},
        {235,16,235}, {235,16,16}, {16,16,235}, {16,16,16},
    };
    for (unsigned y = 0; y < H; y++)
        for (unsigned x = 0; x < W; x++) {
            size_t i = (y * W + x) * 4;
            memcpy(baseline + i, colors[x * 8 / W], 3);
            baseline[i + 3] = 255;
        }
    const uint8_t *pixels = baseline;
    obs_enter_graphics();
    texture = gs_texture_create(W, H, GS_RGBA, 1, &pixels, 0);
    obs_leave_graphics();
    CHECK(texture);
    struct obs_source_info pattern = {
        .id = "ntsc_flatpak_test_pattern", .type = OBS_SOURCE_TYPE_INPUT,
        .output_flags = OBS_SOURCE_VIDEO | OBS_SOURCE_CUSTOM_DRAW,
        .get_name = pattern_name, .create = pattern_create, .destroy = pattern_destroy,
        .get_width = pattern_width, .get_height = pattern_height, .video_render = pattern_render,
    };
    obs_register_source(&pattern);
    source = obs_source_create_private(pattern.id, "isolated-pattern", NULL);
    effect = obs_source_create_private("ntsc_rs_filter", "isolated-filter", NULL);
    CHECK(source && effect);
    props = obs_source_properties(effect);
    CHECK(props);
    obs_set_output_source(0, source);
    obs_add_raw_video_callback(NULL, receive, NULL);
    connected = true;
    CHECK(collect(30, baseline, NULL));
    size_t yellow = (240 * W + 120) * 4;
    CHECK(baseline[yellow] < 50 && baseline[yellow + 1] > 200 && baseline[yellow + 2] > 200);
    obs_source_filter_add(source, effect);
    attached = true;
    unsigned unique = 0;
    CHECK(collect(120, filtered, &unique));
    size_t changed = 0;
    for (size_t i = 0; i < SIZE; i++)
        changed += baseline[i] != filtered[i];
    CHECK(changed > W * H / 10 && unique >= 10);
    obs_source_set_enabled(effect, false);
    CHECK(collect(30, filtered, NULL));
    CHECK(memcmp(baseline, filtered, SIZE) == 0);
    obs_source_set_enabled(effect, true);
    settings = obs_source_get_settings(effect);
    obs_data_set_int(settings, "internal_height", 240);
    obs_source_update(effect, settings);
    CHECK(collect(45, filtered, NULL) && memcmp(baseline, filtered, SIZE) != 0);
    obs_data_set_string(settings, "export_path", preset);
    CHECK(button(props, effect, "export_preset", true));
    obs_data_t *exported = obs_data_create_from_json_file(preset);
    CHECK(exported);
    bool valid = obs_data_get_int(exported, "version") == 1;
    obs_data_release(exported);
    CHECK(valid);
    const char *json = "{\"version\":1,\"luma_smear\":0.123}";
    CHECK(write_file(preset, json));
    obs_data_set_string(settings, "preset_path", preset);
    CHECK(button(props, effect, "import_preset", true));
    CHECK(fabs(obs_data_get_double(settings, "luma_smear") - 0.123) < 0.00001);
    CHECK(button(props, effect, "export_preset", false));
    CHECK(same_file(preset, json));
    obs_data_set_string(settings, "preset_path", denied);
    CHECK(button(props, effect, "import_preset", false));
    CHECK(fabs(obs_data_get_double(settings, "luma_smear") - 0.123) < 0.00001);
    obs_data_set_string(settings, "export_path", denied);
    CHECK(button(props, effect, "export_preset", false));
    obs_data_set_string(settings, "export_path", "/app/ntsc-rs-test-export.json");
    CHECK(button(props, effect, "export_preset", false));
    CHECK(collect(30, filtered, NULL) && memcmp(baseline, filtered, SIZE) != 0);
    result = 0;
done:
    if (connected)
        obs_remove_raw_video_callback(receive, NULL);
    if (started)
        obs_set_output_source(0, NULL);
    if (attached)
        obs_source_filter_remove(source, effect);
    if (props)
        obs_properties_destroy(props);
    if (settings)
        obs_data_release(settings);
    if (effect)
        obs_source_release(effect);
    if (source)
        obs_source_release(source);
    if (texture) {
        obs_enter_graphics();
        gs_texture_destroy(texture);
        obs_leave_graphics();
    }
    if (started)
        obs_shutdown();
    if (display)
        XCloseDisplay(display);
    globfree(&graphics);
    if (!result) {
        /* Only record PASS after normal shutdown; no personal paths in report. */
        char text[1536];
        int size = snprintf(text, sizeof text,
            "{\"result\":\"PASS\",\"runtime\":\"%s\","
            "\"changed_bytes\":%zu,\"unique_effect_frames_in_60_output_frames\":%u,"
            "\"environment\":\"OBS Flatpak Platform (not SDK)\","
            "\"checks\":[\"extension discovery and load\",\"live GPU-CPU-GPU processing\","
            "\"animated noise\",\"bypass\",\"resolution change\",\"Unicode preset export and import\","
            "\"overwrite protection\",\"denied read and write\",\"read-only /app\","
            "\"processing after file errors\",\"clean shutdown\"]}\n",
            runtime, changed, unique);
        if (size < 0 || size >= (int)sizeof text)
            return 1;
        if (!write_file(report, text))
            return 1;
        puts(text);
    }
    return result;
}
