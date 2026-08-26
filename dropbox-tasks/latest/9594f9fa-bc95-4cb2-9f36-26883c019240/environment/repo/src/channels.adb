with Ada.Strings.Unbounded; use Ada.Strings.Unbounded;
with Admission_Rules;

package body Channels is

   -- A subscription is authorized when the tenant's rule covers the whole
   -- channel. A rule the reader cannot make sense of authorizes nothing, and
   -- one unusable rule never stops the rest of the batch from being answered.
   function Authorize_Batch (Requests : Wire.Request_Array)
     return Wire.Decision_Array
   is
      Decisions : Wire.Decision_Array (Requests'Range) := (others => False);
   begin
      for I in Requests'Range loop
         if Admission_Rules.Compile_Rule (To_String (Requests (I).Rule)) then
            Decisions (I) :=
              Admission_Rules.Rule_Admits (To_String (Requests (I).Channel));
         else
            Decisions (I) := False;
         end if;
      end loop;
      return Decisions;
   end Authorize_Batch;

end Channels;
