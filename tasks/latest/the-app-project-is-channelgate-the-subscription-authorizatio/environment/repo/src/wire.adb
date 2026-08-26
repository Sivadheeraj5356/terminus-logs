with Ada.Text_IO;         use Ada.Text_IO;
with GNATCOLL.JSON;       use GNATCOLL.JSON;

package body Wire is

   function Read_Batch return Request_Array_Access is
      Raw   : Unbounded_String;
      Line  : String (1 .. 65536);
      Last  : Natural;
      Doc   : JSON_Value;
      Items : JSON_Array;
      Entry_Value : JSON_Value;
      Result : Request_Array_Access;
   begin
      while not End_Of_File (Standard_Input) loop
         Get_Line (Standard_Input, Line, Last);
         Append (Raw, Line (1 .. Last));
      end loop;

      Doc := Read (To_String (Raw));
      if Doc.Kind /= JSON_Object_Type or else not Doc.Has_Field ("requests")
      then
         return null;
      end if;
      Items := Doc.Get ("requests");
      Result := new Request_Array (1 .. Length (Items));
      for I in 1 .. Length (Items) loop
         Entry_Value := Get (Items, I);
         if Entry_Value.Kind /= JSON_Object_Type
           or else not Entry_Value.Has_Field ("rule")
           or else not Entry_Value.Has_Field ("channel")
         then
            return null;
         end if;
         -- Channels and rules are compared byte by byte, so hand the engine
         -- bytes rather than decoded characters.
         Result (I).Rule := To_Unbounded_String (String'(Entry_Value.Get ("rule")));
         Result (I).Channel :=
           To_Unbounded_String (String'(Entry_Value.Get ("channel")));
      end loop;
      return Result;
   exception
      when others =>
         return null;
   end Read_Batch;

   procedure Write_Decisions (Decisions : Decision_Array) is
      Out_Text : Unbounded_String := To_Unbounded_String ("{""admitted"":[");
   begin
      for I in Decisions'Range loop
         if I > Decisions'First then
            Append (Out_Text, ",");
         end if;
         if Decisions (I) then
            Append (Out_Text, "true");
         else
            Append (Out_Text, "false");
         end if;
      end loop;
      Append (Out_Text, "]}");
      Put_Line (To_String (Out_Text));
   end Write_Decisions;

end Wire;
