# 2D Finite Difference Stencil Discretization Details

This document provides additional reference details on the 2D finite difference scheme used for the wave equation.
Standard second-derivative stencils are derived from Taylor expansions.

For 2nd-order accuracy:
$$f''(x) = \frac{f(x+h) - 2f(x) + f(x-h)}{h^2} + O(h^2)$$

For 4th-order accuracy:
$$f''(x) = \frac{-f(x+2h) + 16f(x+h) - 30f(x) + 16f(x-h) - f(x-2h)}{12h^2} + O(h^4)$$
