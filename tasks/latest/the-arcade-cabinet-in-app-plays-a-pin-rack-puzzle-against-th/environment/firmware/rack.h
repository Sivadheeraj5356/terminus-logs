#ifndef SKAL_RACK_H
#define SKAL_RACK_H

#define FACES 5
#define LATCHES 4
#define BAND 40
#define WMAX (BAND + 1)

typedef struct {
    int rows[2];
    int lanes;
    int face;
    int code;
    int live;
} Rack;

int heavy_ball_armed(int face, int code);
int spread_armed(int face, int code);
int advance_face(int face, int pins);
int filed_code(int pins, int spread);
void spin_up(void);
void normalise(Rack *r);
int throw_legal(const Rack *r, int lane, int pins, int left);
void throw_apply(Rack *r, int lane, int pins, int left);
int house_pick(const Rack *r, int *lane, int *pins, int *left);

#endif
