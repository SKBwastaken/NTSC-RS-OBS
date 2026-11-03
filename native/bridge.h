#pragma once
#include <obs.h>

void *ntsc_engine_create(obs_data_t *settings);
void ntsc_engine_destroy(void *engine);
void ntsc_engine_update(void *engine, obs_data_t *settings);
bool ntsc_submit(void *engine, const uint8_t *pixels, uint32_t stride,
                 uint32_t width, uint32_t height, uint64_t frame);
const uint8_t *ntsc_take(void *engine, uint32_t width, uint32_t height);
void ntsc_defaults(obs_data_t *settings);
void ntsc_properties(obs_properties_t *props);
bool ntsc_import(obs_data_t *settings, const char *path);
bool ntsc_export(obs_data_t *settings, const char *path);

/* Settings bridge. kind: 0 bool, 1 int, 2 float, 3 enum, 4 group. */
double bridge_get(obs_data_t *data, const char *key, int kind);
void bridge_set(obs_data_t *data, const char *key, int kind, double value, bool defaults);
void *bridge_property(obs_properties_t *props, const char *key, const char *label,
                      const char *description, int kind, double min, double max);
void bridge_option(void *property, const char *label, uint32_t value);
void bridge_log(const char *message);
bool bridge_load(void);
uint32_t bridge_version(void);
