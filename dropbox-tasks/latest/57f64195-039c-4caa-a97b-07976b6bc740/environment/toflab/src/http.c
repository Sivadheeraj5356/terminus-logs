#include "http.h"

#include <curl/curl.h>
#include <stdlib.h>
#include <string.h>

struct mem {
    char *data;
    size_t len;
};

static size_t write_cb(char *ptr, size_t size, size_t nmemb, void *userdata) {
    size_t total = size * nmemb;
    struct mem *m = userdata;
    char *n = realloc(m->data, m->len + total + 1);
    if (!n) {
        return 0;
    }
    m->data = n;
    memcpy(m->data + m->len, ptr, total);
    m->len += total;
    m->data[m->len] = '\0';
    return total;
}

json_t *http_get_json(const char *url) {
    CURL *curl = curl_easy_init();
    if (!curl) {
        return NULL;
    }
    struct mem m = {0};
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 0L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &m);
    CURLcode rc = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    curl_easy_cleanup(curl);
    if (rc != CURLE_OK || http_code != 200 || !m.data) {
        free(m.data);
        return NULL;
    }
    json_error_t err;
    json_t *doc = json_loads(m.data, 0, &err);
    free(m.data);
    return doc;
}
