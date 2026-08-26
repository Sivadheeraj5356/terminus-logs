-- channelgate answers channel subscription authorization for the sensor bus. It
-- reads one batch of requests on standard input and writes one decision per
-- request, in order, on standard output.

with Ada.Command_Line;
with Ada.Text_IO;
with Wire; use Wire;
with Channels;

procedure Channelgate is

   task Worker is
      pragma Storage_Size (768 * 1024 * 1024);
   end Worker;

   task body Worker is
      Requests : constant Request_Array_Access := Read_Batch;
   begin
      if Requests = null then
         Ada.Text_IO.Put_Line (Ada.Text_IO.Standard_Error, "decode error");
         Ada.Command_Line.Set_Exit_Status (1);
      else
         Write_Decisions (Channels.Authorize_Batch (Requests.all));
      end if;
   end Worker;

begin
   null;
end Channelgate;
