#include "ac_io.h"

#include <cstdio>
#include <cstring>

int ac_read_ct_volume(const char *path, ac_ct_volume *vol) {
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        return -1;
    }
    unsigned int nx = 0;
    unsigned int ny = 0;
    if (fread(&nx, sizeof nx, 1, fp) != 1 || fread(&ny, sizeof ny, 1, fp) != 1) {
        fclose(fp);
        return -1;
    }
    if (nx != AC_NX || ny != AC_NY) {
        fclose(fp);
        return -1;
    }
    vol->nx = static_cast<int>(nx);
    vol->ny = static_cast<int>(ny);
    if (fread(vol->voxels, 1, AC_NX * AC_NY, fp) != AC_NX * AC_NY) {
        fclose(fp);
        return -1;
    }
    fclose(fp);
    return 0;
}

int ac_write_pressure_wav(const char *path, const ac_pressure_trace *trace, int sr_hz) {
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        return -1;
    }
    const int data_bytes = trace->sample_count * 2;
    const int riff_size = 36 + data_bytes;
    fwrite("RIFF", 1, 4, fp);
    fwrite(&riff_size, 4, 1, fp);
    fwrite("WAVE", 1, 4, fp);
    fwrite("fmt ", 1, 4, fp);
    const int fmt_size = 16;
    const short audio_format = 1;
    const short channels = 1;
    const short bits = 16;
    const int byte_rate = sr_hz * channels * bits / 8;
    const short block_align = channels * bits / 8;
    fwrite(&fmt_size, 4, 1, fp);
    fwrite(&audio_format, 2, 1, fp);
    fwrite(&channels, 2, 1, fp);
    fwrite(&sr_hz, 4, 1, fp);
    fwrite(&byte_rate, 4, 1, fp);
    fwrite(&block_align, 2, 1, fp);
    fwrite(&bits, 2, 1, fp);
    fwrite("data", 1, 4, fp);
    fwrite(&data_bytes, 4, 1, fp);
    for (int i = 0; i < trace->sample_count; ++i) {
        float v = trace->samples[i];
        if (v > 1.0f) {
            v = 1.0f;
        }
        if (v < -1.0f) {
            v = -1.0f;
        }
        short s = static_cast<short>(v * 32767.0f);
        fwrite(&s, 2, 1, fp);
    }
    fclose(fp);
    return 0;
}
