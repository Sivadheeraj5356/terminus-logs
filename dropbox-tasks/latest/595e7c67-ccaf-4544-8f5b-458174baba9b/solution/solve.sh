#!/usr/bin/env bash
set -euo pipefail

B64='I2luY2x1ZGUgImZvbGRlci5ocHAiCgojaW5jbHVkZSA8Y21hdGg+CgpzdGF0aWMgYm9vbCBpc05lZ1plcm8oY29uc3QgTm9kZSogbikgewogIHJldHVybiBuLT5raW5kID09IE5vZGVLaW5kOjpOdW0gJiYgbi0+bnVtID09IDAuMCAmJiBzdGQ6OnNpZ25iaXQobi0+bnVtKTsKfQoKc3RhdGljIGJvb2wgaXNQb3NaZXJvKGNvbnN0IE5vZGUqIG4pIHsKICByZXR1cm4gbi0+a2luZCA9PSBOb2RlS2luZDo6TnVtICYmIG4tPm51bSA9PSAwLjAgJiYgIXN0ZDo6c2lnbmJpdChuLT5udW0pOwp9CgpzdGF0aWMgYm9vbCBpc09uZShjb25zdCBOb2RlKiBuKSB7CiAgcmV0dXJuIG4tPmtpbmQgPT0gTm9kZUtpbmQ6Ok51bSAmJiBuLT5udW0gPT0gMS4wOwp9CgpzdGF0aWMgZG91YmxlIGFwcGx5KE5vZGVLaW5kIGssIGRvdWJsZSB4LCBkb3VibGUgeSkgewogIHN3aXRjaCAoaykgewogICAgY2FzZSBOb2RlS2luZDo6QWRkOgogICAgICByZXR1cm4geCArIHk7CiAgICBjYXNlIE5vZGVLaW5kOjpTdWI6CiAgICAgIHJldHVybiB4IC0geTsKICAgIGNhc2UgTm9kZUtpbmQ6Ok11bDoKICAgICAgcmV0dXJuIHggKiB5OwogICAgY2FzZSBOb2RlS2luZDo6RGl2OgogICAgICByZXR1cm4geCAvIHk7CiAgICBkZWZhdWx0OgogICAgICByZXR1cm4gMC4wOwogIH0KfQoKTm9kZVB0ciBmb2xkKE5vZGVQdHIgbm9kZSkgewogIGlmIChub2RlLT5raW5kID09IE5vZGVLaW5kOjpOdW0gfHwgbm9kZS0+a2luZCA9PSBOb2RlS2luZDo6VmFyKSB7CiAgICByZXR1cm4gbm9kZTsKICB9CiAgaWYgKG5vZGUtPmtpbmQgPT0gTm9kZUtpbmQ6Ok5lZykgewogICAgbm9kZS0+YSA9IGZvbGQoc3RkOjptb3ZlKG5vZGUtPmEpKTsKICAgIGlmIChub2RlLT5hLT5raW5kID09IE5vZGVLaW5kOjpOdW0pIHsKICAgICAgcmV0dXJuIG1ha2VOdW0oLW5vZGUtPmEtPm51bSk7CiAgICB9CiAgICBpZiAobm9kZS0+YS0+a2luZCA9PSBOb2RlS2luZDo6TmVnKSB7CiAgICAgIHJldHVybiBzdGQ6Om1vdmUobm9kZS0+YS0+YSk7CiAgICB9CiAgICByZXR1cm4gbm9kZTsKICB9CiAgbm9kZS0+YSA9IGZvbGQoc3RkOjptb3ZlKG5vZGUtPmEpKTsKICBub2RlLT5iID0gZm9sZChzdGQ6Om1vdmUobm9kZS0+YikpOwogIE5vZGUqIGEgPSBub2RlLT5hLmdldCgpOwogIE5vZGUqIGIgPSBub2RlLT5iLmdldCgpOwogIGlmIChhLT5raW5kID09IE5vZGVLaW5kOjpOdW0gJiYgYi0+a2luZCA9PSBOb2RlS2luZDo6TnVtKSB7CiAgICByZXR1cm4gbWFrZU51bShhcHBseShub2RlLT5raW5kLCBhLT5udW0sIGItPm51bSkpOwogIH0KICBzd2l0Y2ggKG5vZGUtPmtpbmQpIHsKICAgIGNhc2UgTm9kZUtpbmQ6OkFkZDoKICAgICAgaWYgKGlzTmVnWmVybyhhKSkgewogICAgICAgIHJldHVybiBzdGQ6Om1vdmUobm9kZS0+Yik7CiAgICAgIH0KICAgICAgaWYgKGlzTmVnWmVybyhiKSkgewogICAgICAgIHJldHVybiBzdGQ6Om1vdmUobm9kZS0+YSk7CiAgICAgIH0KICAgICAgYnJlYWs7CiAgICBjYXNlIE5vZGVLaW5kOjpTdWI6CiAgICAgIGlmIChpc1Bvc1plcm8oYikpIHsKICAgICAgICByZXR1cm4gc3RkOjptb3ZlKG5vZGUtPmEpOwogICAgICB9CiAgICAgIGJyZWFrOwogICAgY2FzZSBOb2RlS2luZDo6TXVsOgogICAgICBpZiAoaXNPbmUoYSkpIHsKICAgICAgICByZXR1cm4gc3RkOjptb3ZlKG5vZGUtPmIpOwogICAgICB9CiAgICAgIGlmIChpc09uZShiKSkgewogICAgICAgIHJldHVybiBzdGQ6Om1vdmUobm9kZS0+YSk7CiAgICAgIH0KICAgICAgYnJlYWs7CiAgICBjYXNlIE5vZGVLaW5kOjpEaXY6CiAgICAgIGlmIChpc09uZShiKSkgewogICAgICAgIHJldHVybiBzdGQ6Om1vdmUobm9kZS0+YSk7CiAgICAgIH0KICAgICAgYnJlYWs7CiAgICBkZWZhdWx0OgogICAgICBicmVhazsKICB9CiAgcmV0dXJuIG5vZGU7Cn0K'

printf '%s' "$B64" | base64 --decode > /app/src/folder.cpp

cd /app
./build.sh

check() {
  prog="$1"
  want="$2"
  got="$(printf '%s\n' "$prog" | /app/foldc)"
  if [ "$got" != "$want" ]; then
    echo "oracle smoke check failed for [$prog]: got [$got] want [$want]"
    exit 1
  fi
}

check 'x + 0.0' '(x + 0.0)'
check 'x + -0.0' 'x'
check 'x - 0.0' 'x'
check 'x - -0.0' '(x - -0.0)'
check 'x * 0.0' '(x * 0.0)'
check 'x * 1.0' 'x'
check 'x - x' '(x - x)'
check '-2.0 * 0.0' '-0.0'
check 'x * (3.0 - 3.0)' '(x * 0.0)'
check '(x + 1.0) + 2.0' '((x + 1.0) + 2.0)'
echo "oracle build and smoke run OK"
