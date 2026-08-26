# telemetrybus 3.1.0 migration notes

Report(event string) error is no longer exported. Reporters open a window
with Open() (*Window, error), buffer an outgoing frame with
Window.Queue(event string) error, and deliver whatever is pending with
Window.Flush(ctx context.Context) error; Window.Close() releases the window
once a reporter is done with it.

Queue reports an oversized frame immediately, before Flush does any work,
and leaves the pending batch unchanged when it rejects a frame. Flush
reports a context that is already done the same way, before clearing
anything it was holding.

Delivery is slot-addressed in 3.1.0. The bus stamps every frame it accepts
with the next slot in the delivering window's run, and a window opened with
Open() begins its run at slot 0; Delivered() reports the frames a process
has delivered, in order, with the slot each one carried. A window delivers
at most WindowCapacity frames before it is full, and Queue on a full window
reports ErrWindowFull without buffering anything; OpenAt(slot) opens a
window whose run begins at slot rather than at 0. Before 3.1.0 a process
reached the bus through the one package-level Report, so a process's
deliveries form one continuous run of slots from 0. MaxFrameBytes is
unchanged from the pre-3.1.0 line.

A process may not open more than MaxWindowsPerProcess windows over its
life; Open and OpenAt both draw from that same budget, closing a window
does not return its share, and either call reports ErrTooManyWindows once
the budget is spent.
