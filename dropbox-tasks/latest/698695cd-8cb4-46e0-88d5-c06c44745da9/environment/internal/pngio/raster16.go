package pngio

import (
	"image"
	_ "image/png"
	"os"
)

type Frame struct {
	Width  int
	Height int
	Data   []uint16
}

func ReadGray16(path string) (*Frame, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	img, _, err := image.Decode(f)
	if err != nil {
		return nil, err
	}
	b := img.Bounds()
	w, h := b.Dx(), b.Dy()
	data := make([]uint16, w*h)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			_, _, _, a := img.At(b.Min.X+x, b.Min.Y+y).RGBA()
			data[y*w+x] = uint16(a >> 8)
		}
	}
	return &Frame{Width: w, Height: h, Data: data}, nil
}
