-- The policy layer of the telemetry bus.

with Wire;

package Channels is

   function Authorize_Batch (Requests : Wire.Request_Array)
     return Wire.Decision_Array;

end Channels;
