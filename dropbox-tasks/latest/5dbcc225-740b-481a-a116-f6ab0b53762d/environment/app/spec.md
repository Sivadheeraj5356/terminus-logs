# Polar Modulated Deformable CNN with Grouped Weight Standardization & Spectral Normalization Layer Specifications

This document defines the mathematical formulations, shapes, and specifications for the `DeformableConv2D` (Polar Modulated Grouped Deformable Convolution with Grouped Weight Standardization, Grouped Spectral Normalization, Björck Orthogonalization, Internal Offset Prediction, and Bicubic Spline Interpolation), `GroupEvoNorm2D`, and `BlurPool2D` layers.

---

## 1. Polar Modulated Grouped Deformable Conv2D Layer

### Shapes
- **Input:** Tensor of shape `(InChannels, H, W)`
- **Weights:** Flat float64 slice of size `OutChannels * (InChannels / Groups) * KernelSize * KernelSize` (internally standardized and normalized per group)
- **Biases:** Flat float64 slice of size `OutChannels`
- **OffsetWeights:** Flat float64 slice of size `(3 * KernelSize * KernelSize) * InChannels * KernelSize * KernelSize`
- **OffsetBiases:** Flat float64 slice of size `3 * KernelSize * KernelSize`
- **SplineAlpha:** Flat float64 slice of size `InChannels` (initialized to -0.5)
- **Output:** Tensor of shape `(OutChannels, H_out, W_out)`

### 1.1 Grouped Weight Standardization, Spectral Normalization, and Björck Orthogonalization
To stabilize training and enforce strict orthogonal constraints, the raw weight parameters `Weights` are convolved after applying **Weight Standardization**, **Spectral Normalization**, and **Björck Orthogonalization**:
1. The layer operates with a parameter $G$ (`Groups`) which must divide both `InChannels` and `OutChannels`.
2. Let $C_{in\_g} = \text{InChannels} / G$ and $C_{out\_g} = \text{OutChannels} / G$.
3. The weights matrix is divided into $G$ independent groups. For each group $g \in \{0, \dots, G-1\}$, the raw weight sub-matrix $W^{(g)}$ has shape $M_g \times N_g$, where $M_g = C_{out\_g}$ and $N_g = C_{in\_g} \times \text{KernelSize} \times \text{KernelSize}$.
4. Apply **Weight Standardization** along the rows of each group matrix $W^{(g)}$ to obtain the standardized group weight matrix $\hat{W}^{(g)}$:
   For each row $i \in \{0, \dots, M_g-1\}$ and column $j \in \{0, \dots, N_g-1\}$:
   $$\mu_{g,i} = \frac{1}{N_g} \sum_{k=0}^{N_g-1} W^{(g)}_{i,k}$$
   $$\sigma_{g,i}^2 = \frac{1}{N_g} \sum_{k=0}^{N_g-1} (W^{(g)}_{i,k} - \mu_{g,i})^2$$
   $$\hat{W}^{(g)}_{i,j} = \frac{W^{(g)}_{i,j} - \mu_{g,i}}{\sqrt{\sigma_{g,i}^2 + 10^{-5}}}$$
5. The spectral norm $\sigma_g = \sigma(\hat{W}^{(g)})$ is the largest singular value of the standardized group weight matrix $\hat{W}^{(g)}$. It is computed iteratively using the **Power Iteration** method:
   - Initialize $u^{(g)} \in \mathbb{R}^{M_g}$ and $v^{(g)} \in \mathbb{R}^{N_g}$ to all $1.0$ on the first forward pass.
   - For 5 iterations, compute:
     $$v^{(g)} \leftarrow (\hat{W}^{(g)})^T u^{(g)}, \quad v^{(g)} \leftarrow \frac{v^{(g)}}{\|v^{(g)}\|_2}$$
     $$u^{(g)} \leftarrow \hat{W}^{(g)} v^{(g)}, \quad u^{(g)} \leftarrow \frac{u^{(g)}}{\|u^{(g)}\|_2}$$
   - The estimated spectral norm is:
     $$\sigma_g = (u^{(g)})^T \hat{W}^{(g)} v^{(g)}$$
6. Initialize the orthogonalization sequence for group $g$ using the spectral normalized weights:
   $$W_0^{(g)} = \frac{\hat{W}^{(g)}}{\sigma_g}$$
7. Apply 3 iterations of **Björck Orthogonalization** to project $W_0^{(g)}$ to a row-orthogonal matrix:
   For $t \in \{0, 1, 2\}$:
   $$W_{t+1}^{(g)} = 1.5 W_t^{(g)} - 0.5 W_t^{(g)} (W_t^{(g)})^T W_t^{(g)}$$
8. The final normalized weights matrix for group $g$ is:
   $$\tilde{W}^{(g)} = W_3^{(g)}$$
9. The power iteration vectors $u^{(g)}$ and $v^{(g)}$ must be saved and persist across forward passes in the global slices `U` (size `OutChannels`) and `V` (size `InChannels * KernelSize * KernelSize`).
   - $u^{(g)}$ is stored in `U[g * M_g : (g+1) * M_g]`.
   - $v^{(g)}$ is stored in `V[g * N_g : (g+1) * N_g]`.

### 1.2 Internal Offset and Mask Prediction
The offsets and masks are predicted dynamically from the input tensor $X$ using a standard 2D convolution layer inside the `DeformableConv2D` layer:
- Let $C_{off} = 3 \times \text{KernelSize}^2$ be the number of output channels for the offset predictor.
- The predictor has weights `OffsetWeights` of shape $C_{off} \times \text{InChannels} \times \text{KernelSize} \times \text{KernelSize}$ and biases `OffsetBiases` of shape $C_{off}$.
- The convolution uses the same `Stride` and `Padding` as the main convolution.
- For each output channel $c_{off} \in \{0, \dots, C_{off}-1\}$ and spatial output position $(oh, ow)$:
  $$P_{c_{off}, oh, ow} = \text{OffsetBiases}_{c_{off}} + \sum_{ic=0}^{\text{InChannels}-1} \sum_{kh=0}^{\text{KernelSize}-1} \sum_{kw=0}^{\text{KernelSize}-1} \text{OffsetWeights}_{c_{off}, ic, kh, kw} \cdot X_{ic, oh \cdot \text{Stride} - \text{Padding} + kh, ow \cdot \text{Stride} - \text{Padding} + kw}$$
  where any coordinate outside the input spatial boundaries evaluates to $0.0$.
- The first $2 \times \text{KernelSize}^2$ channels of $P$ correspond to the raw offsets. Specifically, for kernel index $k = kh \cdot \text{KernelSize} + kw$:
  - $o_r$ is at channel $2k$: $o_r(k, oh, ow) = P_{2k, oh, ow}$
  - $o_\theta$ is at channel $2k+1$: $o_\theta(k, oh, ow) = P_{2k+1, oh, ow}$
- The last $\text{KernelSize}^2$ channels of $P$ correspond to the raw masks. Specifically, for kernel index $k = kh \cdot \text{KernelSize} + kw$:
  - The raw mask parameter is at channel $2 \times \text{KernelSize}^2 + k$: $raw\_m(k, oh, ow) = P_{2 \times \text{KernelSize}^2 + k, oh, ow}$

### 1.3 Mathematical Formulations (Forward Pass)
For each output channel $oc \in \{0, \dots, \text{OutChannels}-1\}$ and spatial coordinates $(oh, ow)$:
$$Y_{oc, oh, ow} = \text{Biases}_{oc} + \sum_{ic_{local}=0}^{C_{in\_g}-1} \sum_{kh=0}^{\text{KernelSize}-1} \sum_{kw=0}^{\text{KernelSize}-1} \tilde{W}^{(g)}_{oc_{local}, ic_{local}, kh, kw} \cdot \text{Bicubic}(X, ic, y_a, x_a) \cdot m_{kh, kw, oh, ow}$$

Where:
- $g = \lfloor oc / C_{out\_g} \rfloor$ and $oc_{local} = oc \pmod{C_{out\_g}}$.
- The corresponding input channel is $ic = g \cdot C_{in\_g} + ic_{local}$.
- Let $kh_c = (\text{KernelSize}-1)/2$ and $kw_c = (\text{KernelSize}-1)/2$ be the spatial center indices of the kernel.
- For each kernel offset $(kh, kw)$, compute its nominal displacement relative to the kernel center in polar coordinates:
  $$dy_k = kh - kh_c, \quad dx_k = kw - kw_c$$
  $$r_k = \sqrt{dy_k^2 + dx_k^2}$$
  $$\theta_k = \text{atan2}(dy_k, dx_k)$$
  *(where $\text{atan2}(0, 0) = 0.0$)*.

- Let $k = kh \cdot \text{KernelSize} + kw$ be the flat kernel index.
- The actual radial offset $\Delta r$ and angular offset $\Delta \theta$ are warped using a scaled hyperbolic tangent:
  $$\Delta r = 2.0 \cdot \tanh(o_r(k, oh, ow))$$
  $$\Delta \theta = \pi \cdot \tanh(o_\theta(k, oh, ow))$$
- The nominal coordinate center for the kernel window is:
  $$y_{\text{center}} = oh \cdot \text{Stride} - \text{Padding} + kh_c$$
  $$x_{\text{center}} = ow \cdot \text{Stride} - \text{Padding} + kw_c$$
- The actual sampling coordinate $(y_a, x_a)$ is computed by warping the grid in polar space:
  $$R_k = r_k + \Delta r$$
  $$\Theta_k = \theta_k + \Delta \theta$$
  $$y_a = y_{\text{center}} + R_k \sin(\Theta_k)$$
  $$x_a = x_{\text{center}} + R_k \cos(\Theta_k)$$

- The modulation mask is computed from the raw mask parameters using a sigmoid activation:
  $$m_{kh, kw, oh, ow} = \text{sigmoid}(raw\_m(k, oh, ow))$$
  where $\text{sigmoid}(z) = 1 / (1 + e^{-z})$.

- The function $\text{Bicubic}(X, ic, y, x)$ evaluates the input tensor $X$ at floating-point coordinates $(y, x)$ using Keys' Bicubic Spline Interpolation:
  Let $y_0 = \lfloor y \rfloor$, $x_0 = \lfloor x \rfloor$.
  Let $dy = y - y_0$, $dx = x - x_0$.
  Let $a = \text{SplineAlpha}[ic]$.
  The interpolation weight function $R(t)$ is defined as:
  $$R(t) = \begin{cases} (a+2)|t|^3 - (a+3)|t|^2 + 1 & \text{for } |t| \le 1 \\ a|t|^3 - 5a|t|^2 + 8a|t| - 4a & \text{for } 1 < |t| < 2 \\ 0 & \text{otherwise} \end{cases}$$
  The interpolated value is:
  $$\text{Bicubic}(X, ic, y, x) = \sum_{m=-1}^2 \sum_{n=-1}^2 X_{ic, y_0+m, x_0+n} \cdot R(m - dy) \cdot R(n - dx)$$
  where any grid coordinate $(h, w)$ outside the spatial boundaries $[0, H-1] \times [0, W-1]$ evaluates to $0.0$.

### 1.4 State Exposure Requirements
To facilitate verification and testing, the `DeformableConv2D` struct exposed fields must be populated during the forward pass:
- `tildeW`: Must contain the final standardized, normalized, and Björck-orthogonalized weights slice of size `OutChannels * (InChannels/Groups) * KernelSize * KernelSize`.
- `hatW`: Must contain the standardized weights slice of size `OutChannels * (InChannels/Groups) * KernelSize * KernelSize`.
- `mu`: Must contain the row-wise means of size `OutChannels`.
- `varVal`: Must contain the row-wise variances of size `OutChannels`.
- `U` and `V`: Must store the singular vectors from the power iterations.
- `bjorckW`: Must store the intermediate Björck orthogonalization weight slices of size `3` (each of size `OutChannels * (InChannels/Groups) * KernelSize * KernelSize`).

### Output Dimensions
- $H_{\text{out}} = \lfloor (H - \text{KernelSize} + 2 \times \text{Padding}) / \text{Stride} \rfloor + 1$
- $W_{\text{out}} = \lfloor (W - \text{KernelSize} + 2 \times \text{Padding}) / \text{Stride} \rfloor + 1$

---

## 2. GroupEvoNorm2D Layer

### Shapes and Parameters
- **Input:** Tensor of shape `(Channels, H, W)`
- **Gammas:** Flat float64 slice of size `Channels` (initialized to `1.0`)
- **Betas:** Flat float64 slice of size `Channels` (initialized to `0.0`)
- **Output:** Tensor of shape `(Channels, H, W)`

### Mathematical Formulations (Forward Pass)

1. **Group Splitting:**
   The `Channels` are divided into `NumGroups` groups. Each group contains $C_g = \text{Channels} / \text{NumGroups}$ channels.

2. **Group Mean and Variance:**
   For each group $g \in \{0, \dots, \text{NumGroups} - 1\}$, the mean $\mu_g$ and variance $\sigma_g^2$ are computed across all channels in the group and all spatial positions ($H \times W$):
   $$\mu_g = \frac{1}{N} \sum_{c \in \text{group } g} \sum_{h=0}^{H-1} \sum_{w=0}^{W-1} X_{c, h, w}$$
   $$\sigma_g^2 = \frac{1}{N} \sum_{c \in \text{group } g} \sum_{h=0}^{H-1} \sum_{w=0}^{W-1} (X_{c, h, w} - \mu_g)^2$$
   where $N = C_g \times H \times W$.

3. **EvoNorm-S0 Normalization:**
   The layer maintains an additional learnable parameter vector **V** (flat float64 slice of size `Channels`, initialized to `1.0`).
   $$\hat{X}_{c, h, w} = \frac{X_{c, h, w} \cdot \text{sigmoid}(V_c \cdot X_{c, h, w})}{\sqrt{\sigma_g^2 + \epsilon}}$$
   where $\epsilon = 10^{-5}$.

4. **Scale and Shift:**
   $$Y_{c, h, w} = \gamma_c \hat{X}_{c, h, w} + \beta_c$$

---

## 3. BlurPool2D Layer

### Shapes and Parameters
- **Input:** Tensor of shape `(C, H, W)`
- **Output:** Tensor of shape `(C, H_out, W_out)`

### Mathematical Formulations (Forward Pass)

The `BlurPool2D` layer operates in two consecutive steps:

1. **Dense Max Pooling:**
   Apply Max Pooling with `PoolSize` and a stride of 1 (no padding).
   $$M_{c, h, w} = \max_{m,n \in \{0, \dots, \text{PoolSize}-1\}} X_{c, h + m, w + n}$$
   The intermediate tensor $M$ has shape $H_m = H - \text{PoolSize} + 1$ and $W_m = W - \text{PoolSize} + 1$.

2. **Binomial Blur Filter:**
   Apply a fixed $3 \times 3$ blur filter with stride `Stride` and padding 1 (out-of-bounds coordinates of $M$ are treated as $0.0$).
   The blur kernel $B$ is:
   $$B = \frac{1}{16} \begin{bmatrix} 1 & 2 & 1 \\ 2 & 4 & 2 \\ 1 & 2 & 1 \end{bmatrix}$$
   The final output is computed as:
   $$Y_{c, h_{out}, w_{out}} = \sum_{i=0}^2 \sum_{j=0}^2 B_{i, j} \cdot M_{c, h_{out} \cdot \text{Stride} - 1 + i, w_{out} \cdot \text{Stride} - 1 + j}$$
   
   The output dimensions are:
   - $H_{\text{out}} = \lfloor (H_m + 2 \times 1 - 3) / \text{Stride} \rfloor + 1 = \lfloor (H_m - 1) / \text{Stride} \rfloor + 1$
   - $W_{\text{out}} = \lfloor (W_m + 2 \times 1 - 3) / \text{Stride} \rfloor + 1 = \lfloor (W_m - 1) / \text{Stride} \rfloor + 1$

---

## 4. Backward Pass Requirements
For all three layers, you must derive and implement the analytical backward pass to compute gradients of the loss w.r.t their inputs and all learnable parameters. All analytical gradients w.r.t raw parameters (including weights, biases, offset weights, offset biases, gammas, betas) and input tensors must be derived from first principles using standard calculus chain rule derivatives.

---

## 5. Updates and General Rules
- Parameters ($P$) are updated using: $P = P - \text{lr} \times dP$.
- Accumulate gradients during backward passes and clear them during the `Update` call.

---

## 6. Model Training Convergence Gate
The verifier constructs a sequential network with the following architecture:
- Input shape: `(2, 8, 8)`
- `DeformableConv2D` layer (2 in-channels, 4 out-channels, kernel size 3, stride 1, padding 1, groups 2)
- `GroupEvoNorm2D` layer (4 channels, 2 groups)
- `BlurPool2D` layer (pool size 2, stride 2, resulting in output shape `(4, 4, 4)`)
- `Dense` layer (input size 64, output size 2)
- `SoftmaxCrossEntropy` loss

The network is trained on a synthetic dataset of 4 samples (binary classification) for 30 epochs using a constant learning rate of 0.05. The final average cross-entropy training loss at epoch 30 must be strictly below 0.1.
