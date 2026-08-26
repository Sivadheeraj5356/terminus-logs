#include <stdint.h>

__attribute__((section(".note.wit"), used))
static const uint32_t kq_wit_note_words[] = {14U, 0U};

volatile uint32_t kq_wit_export = 18U;

int kq_wit_entry(void) {
    return (int)kq_wit_export;
}
