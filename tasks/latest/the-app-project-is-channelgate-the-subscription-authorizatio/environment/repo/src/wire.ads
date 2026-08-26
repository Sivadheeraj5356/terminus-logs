-- Framing for the channel admission CLI: one JSON batch in on standard input,
-- one JSON object of decisions out on standard output.

with Ada.Strings.Unbounded; use Ada.Strings.Unbounded;

package Wire is

   type Request is record
      Rule    : Unbounded_String;
      Channel : Unbounded_String;
   end record;

   type Request_Array is array (Positive range <>) of Request;
   type Request_Array_Access is access Request_Array;

   type Decision_Array is array (Positive range <>) of Boolean;

   function Read_Batch return Request_Array_Access;

   procedure Write_Decisions (Decisions : Decision_Array);

end Wire;
