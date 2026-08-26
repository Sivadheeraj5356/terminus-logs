-- The rule language is read into a small tree and the tree is walked against
-- the channel; the whole channel must be covered for the subscription to be
-- authorized.

package body Admission_Rules is

   Max_Nodes  : constant := 4096;
   Max_Kids   : constant := 512;
   Max_Groups : constant := 63;

   type Kind_Type is
     (K_Lit, K_Any, K_Class, K_Cat, K_Alt, K_Rep, K_Cnt, K_Grp, K_Ref);

   type Member_Set is array (0 .. 255) of Boolean;
   type Kid_Pool_Array is array (1 .. Max_Kids) of Natural;

   type Node_Type is record
      Kind       : Kind_Type := K_Lit;
      Ch         : Integer   := 0;
      Neg        : Boolean   := False;
      Members    : Member_Set := (others => False);
      Kids_Start : Natural   := 0;
      Kids_Count : Natural   := 0;
      Body_Node  : Integer   := -1;
      Again      : Character := ' ';
      Least      : Natural   := 0;
      Most       : Natural   := 0;
      Unbounded  : Boolean   := False;
      Idx        : Natural   := 0;
   end record;

   type Node_Array is array (1 .. Max_Nodes) of Node_Type;

   type Caps_Array is array (0 .. 2 * Max_Groups + 1) of Integer;

   type Op_Type is (O_Char, O_Any, O_Class, O_Split, O_Jmp, O_Match);

   Max_Steps : constant := 8192;

   type Step_Type is record
      Op         : Op_Type := O_Match;
      Ch         : Integer := 0;
      Class_Node : Integer := -1;
      X          : Integer := 0;
      Y          : Integer := 0;
   end record;

   type Step_Array is array (0 .. Max_Steps) of Step_Type;
   type Step_Array_Access is access Step_Array;

   type Plan_Record is record
      Steps : Step_Array_Access := null;
      Count : Natural := 0;
   end record;

   type Plan_Array is array (1 .. Max_Nodes) of Plan_Record;
   type Index_Array is array (0 .. Max_Steps) of Natural;
   type Seen_Array is array (0 .. Max_Steps) of Boolean;
   type Stop_Array is array (0 .. 65536) of Natural;
   type Stop_Array_Access is access Stop_Array;

   type Resume_Kind is (R_Done, R_Seq, R_Star, R_Plus, R_Cnt, R_COpt, R_Grp);

   type Resume_Point;
   type Resume_Access is access all Resume_Point;

   type Resume_Point is record
      Kind : Resume_Kind := R_Done;
      Node : Natural       := 0;
      Step : Integer       := 0;
      From : Integer       := 0;
      Next : Resume_Access := null;
   end record;

   Nodes      : Node_Array;
   Node_Count : Natural := 0;
   Kid_Pool   : Kid_Pool_Array;
   Kid_Used   : Natural := 0;

   Src      : String (1 .. 4096);
   Src_Len  : Natural := 0;
   Src_Pos  : Natural := 0;
   Groups   : Natural := 0;
   Ok       : Boolean := True;
   Root     : Natural := 0;

   Subject     : String (1 .. 65536);
   Subject_Len : Natural := 0;

   Ref_Slots  : array (0 .. 9) of Boolean := (others => False);
   Free_Cache : array (1 .. Max_Nodes) of Integer := (others => -1);
   Plans      : Plan_Array;

   function Read_Alt return Natural;
   function Admit_Node
     (N : Natural; Pos : Integer; Caps : Caps_Array; K : Resume_Access)
      return Boolean;
   function Admit_Star
     (Body_Node : Natural; Pos : Integer; Caps : Caps_Array; K : Resume_Access)
      return Boolean;
   function Admit_Counted
     (N : Natural; Remaining : Integer; Pos : Integer; Caps : Caps_Array;
      K : Resume_Access) return Boolean;
   function Admit_Counted_Opt
     (N : Natural; Opt : Integer; Pos : Integer; Caps : Caps_Array;
      K : Resume_Access) return Boolean;
   function Resume
     (K : Resume_Access; Pos : Integer; Caps : Caps_Array) return Boolean;
   function Slot_Free (N : Natural) return Boolean;
   procedure Plan_Compile
     (Steps : Step_Array_Access; Count : in out Natural; N : Natural);

   function New_Node (A_Kind : Kind_Type) return Natural is
   begin
      if Node_Count >= Max_Nodes then
         Ok := False;
         return 1;
      end if;
      Node_Count := Node_Count + 1;
      Nodes (Node_Count) := (Kind => A_Kind, others => <>);
      return Node_Count;
   end New_Node;

   function Lit_Node (Ch : Integer) return Natural is
      N : constant Natural := New_Node (K_Lit);
   begin
      Nodes (N).Ch := Ch;
      return N;
   end Lit_Node;

   -- ---- rule reader ----

   function At_Off (Off : Natural) return Character is
   begin
      if Src_Pos + Off < Src_Len then
         return Src (Src_Pos + Off + 1);
      end if;
      return Character'Val (0);
   end At_Off;

   procedure Read_Num (Has : out Boolean; Value : out Integer) is
      Start : constant Natural := Src_Pos;
   begin
      Value := 0;
      while Src_Pos < Src_Len and then At_Off (0) in '0' .. '9' loop
         Src_Pos := Src_Pos + 1;
      end loop;
      if Src_Pos = Start then
         Has := False;
         return;
      end if;
      for I in Start .. Src_Pos - 1 loop
         Value := Value * 10 + (Character'Pos (Src (I + 1)) - 48);
      end loop;
      Has := True;
   end Read_Num;

   function Read_Counted (Atom : Natural) return Natural is
      Start   : constant Natural := Src_Pos;
      Lo, Hi  : Integer;
      Has_Lo  : Boolean;
      Has_Hi  : Boolean;
      N       : Natural;
   begin
      Src_Pos := Src_Pos + 1;
      Read_Num (Has_Lo, Lo);
      if Src_Pos < Src_Len and then At_Off (0) = '}' then
         Src_Pos := Src_Pos + 1;
         if not Has_Lo then
            Src_Pos := Start + 1;
            return Lit_Node (123);
         end if;
         N := New_Node (K_Cnt);
         Nodes (N).Body_Node := Atom;
         Nodes (N).Least := Lo;
         Nodes (N).Most := Lo;
         return N;
      end if;
      if Src_Pos < Src_Len and then At_Off (0) = ',' then
         Src_Pos := Src_Pos + 1;
         Read_Num (Has_Hi, Hi);
         if Src_Pos < Src_Len and then At_Off (0) = '}' then
            Src_Pos := Src_Pos + 1;
            if not Has_Lo then
               Lo := 0;
            end if;
            N := New_Node (K_Cnt);
            Nodes (N).Body_Node := Atom;
            Nodes (N).Least := Lo;
            Nodes (N).Most := Hi;
            Nodes (N).Unbounded := not Has_Hi;
            return N;
         end if;
      end if;
      Src_Pos := Start + 1;
      return Lit_Node (123);
   end Read_Counted;

   function Read_Class return Natural is
      N     : Natural;
      Ch    : Integer;
      Hi    : Integer;
      First : Boolean := True;
   begin
      Src_Pos := Src_Pos + 1;
      N := New_Node (K_Class);
      if Src_Pos < Src_Len and then At_Off (0) = '^' then
         Nodes (N).Neg := True;
         Src_Pos := Src_Pos + 1;
      end if;
      while Src_Pos < Src_Len and then (At_Off (0) /= ']' or else First) loop
         First := False;
         Ch := Character'Pos (At_Off (0));
         if Src_Pos + 2 < Src_Len and then At_Off (1) = '-'
           and then At_Off (2) /= ']'
         then
            Hi := Character'Pos (At_Off (2));
            for B in Ch .. Hi loop
               Nodes (N).Members (B) := True;
            end loop;
            Src_Pos := Src_Pos + 3;
         else
            Nodes (N).Members (Ch) := True;
            Src_Pos := Src_Pos + 1;
         end if;
      end loop;
      if Src_Pos >= Src_Len or else At_Off (0) /= ']' then
         Ok := False;
         return N;
      end if;
      Src_Pos := Src_Pos + 1;
      return N;
   end Read_Class;

   function Read_Atom return Natural is
      C, D      : Character;
      Idx       : Natural;
      Body_Node : Natural;
      N         : Natural;
   begin
      if Src_Pos >= Src_Len then
         Ok := False;
         return Lit_Node (0);
      end if;
      C := At_Off (0);
      if C = '(' then
         Src_Pos := Src_Pos + 1;
         Groups := Groups + 1;
         Idx := Groups;
         Body_Node := Read_Alt;
         if not Ok or else Src_Pos >= Src_Len or else At_Off (0) /= ')' then
            Ok := False;
            return Body_Node;
         end if;
         Src_Pos := Src_Pos + 1;
         N := New_Node (K_Grp);
         Nodes (N).Idx := Idx;
         Nodes (N).Body_Node := Body_Node;
         return N;
      end if;
      if C = '[' then
         return Read_Class;
      end if;
      if C = '.' then
         Src_Pos := Src_Pos + 1;
         return New_Node (K_Any);
      end if;
      if C = '\' then
         Src_Pos := Src_Pos + 1;
         if Src_Pos >= Src_Len then
            Ok := False;
            return Lit_Node (0);
         end if;
         D := At_Off (0);
         if D < '1' or else D > '9' then
            Ok := False;
            return Lit_Node (0);
         end if;
         Src_Pos := Src_Pos + 1;
         N := New_Node (K_Ref);
         Nodes (N).Idx := Character'Pos (D) - 48;
         return N;
      end if;
      if C = ')' or else C = '*' or else C = '+' or else C = '?'
        or else C = '|'
      then
         Ok := False;
         return Lit_Node (0);
      end if;
      Src_Pos := Src_Pos + 1;
      return Lit_Node (Character'Pos (C));
   end Read_Atom;

   function Read_Repeat return Natural is
      Atom : constant Natural := Read_Atom;
      C    : Character;
      N    : Natural;
   begin
      if not Ok then
         return Atom;
      end if;
      if Src_Pos < Src_Len then
         C := At_Off (0);
         if C = '*' or else C = '+' or else C = '?' then
            Src_Pos := Src_Pos + 1;
            N := New_Node (K_Rep);
            Nodes (N).Body_Node := Atom;
            Nodes (N).Again := C;
            return N;
         end if;
         if C = '{' then
            return Read_Counted (Atom);
         end if;
      end if;
      return Atom;
   end Read_Repeat;

   function Store_Kids (Local : Kid_Pool_Array; Count : Natural) return Natural is
      Start : constant Natural := Kid_Used + 1;
   begin
      if Kid_Used + Count > Max_Kids then
         Ok := False;
         return Start;
      end if;
      for I in 1 .. Count loop
         Kid_Pool (Kid_Used + I) := Local (I);
      end loop;
      Kid_Used := Kid_Used + Count;
      return Start;
   end Store_Kids;

   function Read_Concat return Natural is
      Local : Kid_Pool_Array;
      Count : Natural := 0;
      N     : Natural;
   begin
      while Ok and then Src_Pos < Src_Len and then At_Off (0) /= '|'
        and then At_Off (0) /= ')'
      loop
         exit when Count >= Max_Kids;
         Count := Count + 1;
         Local (Count) := Read_Repeat;
      end loop;
      if Count = 1 then
         return Local (1);
      end if;
      N := New_Node (K_Cat);
      Nodes (N).Kids_Start := Store_Kids (Local, Count);
      Nodes (N).Kids_Count := Count;
      return N;
   end Read_Concat;

   function Read_Alt return Natural is
      Local : Kid_Pool_Array;
      Count : Natural := 1;
      N     : Natural;
   begin
      Local (1) := Read_Concat;
      while Ok and then Src_Pos < Src_Len and then At_Off (0) = '|' loop
         exit when Count >= Max_Kids;
         Src_Pos := Src_Pos + 1;
         Count := Count + 1;
         Local (Count) := Read_Concat;
      end loop;
      if Count = 1 then
         return Local (1);
      end if;
      N := New_Node (K_Alt);
      Nodes (N).Kids_Start := Store_Kids (Local, Count);
      Nodes (N).Kids_Count := Count;
      return N;
   end Read_Alt;

   -- ---- capture-reference survey ----

   procedure Collect_Referenced (N : Natural) is
   begin
      case Nodes (N).Kind is
         when K_Ref =>
            if Nodes (N).Idx <= 9 then
               Ref_Slots (Nodes (N).Idx) := True;
            end if;
         when K_Cat | K_Alt =>
            for I in 0 .. Nodes (N).Kids_Count - 1 loop
               Collect_Referenced (Kid_Pool (Nodes (N).Kids_Start + I));
            end loop;
         when K_Rep | K_Cnt | K_Grp =>
            Collect_Referenced (Nodes (N).Body_Node);
         when others =>
            null;
      end case;
   end Collect_Referenced;

   -- A subtree can be handed to the sweep only when no capture span it produces
   -- is read back later in the rule.
   function Slot_Free (N : Natural) return Boolean is
      Verdict : Boolean := True;
   begin
      if Free_Cache (N) >= 0 then
         return Free_Cache (N) = 1;
      end if;
      case Nodes (N).Kind is
         when K_Ref =>
            Verdict := False;
         when K_Grp =>
            if Nodes (N).Idx <= 9 and then Ref_Slots (Nodes (N).Idx) then
               Verdict := False;
            else
               Verdict := Slot_Free (Nodes (N).Body_Node);
            end if;
         when K_Cat | K_Alt =>
            for I in 0 .. Nodes (N).Kids_Count - 1 loop
               if not Slot_Free (Kid_Pool (Nodes (N).Kids_Start + I)) then
                  Verdict := False;
                  exit;
               end if;
            end loop;
         when K_Rep | K_Cnt =>
            Verdict := Slot_Free (Nodes (N).Body_Node);
         when others =>
            null;
      end case;
      if Verdict then
         Free_Cache (N) := 1;
      else
         Free_Cache (N) := 0;
      end if;
      return Verdict;
   end Slot_Free;

   -- ---- single-sweep step table ----
   --
   -- A subtree carrying no capture that is read back later is turned into a
   -- small step table and advanced one position at a time over the whole
   -- channel, so the number of live steps stays bounded by the size of the
   -- table instead of by the number of ways the channel can be divided among
   -- the repetitions.

   function Plan_Emit
     (Steps : Step_Array_Access; Count : in out Natural; A_Op : Op_Type;
      A_Ch : Integer; A_Class : Integer; A_X : Integer; A_Y : Integer)
      return Integer
   is
      Slot : constant Natural := Count;
   begin
      if Count > Max_Steps then
         return Max_Steps;
      end if;
      Steps (Slot) := (Op => A_Op, Ch => A_Ch, Class_Node => A_Class,
                       X => A_X, Y => A_Y);
      Count := Count + 1;
      return Slot;
   end Plan_Emit;

   procedure Plan_Compile
     (Steps : Step_Array_Access; Count : in out Natural; N : Natural)
   is
      Sp     : Integer;
      Start  : Integer;
      Jmps   : Index_Array;
      NJmp   : Natural := 0;
      Splits : Index_Array;
      NSplit : Natural := 0;
      Ignore : Integer;
   begin
      case Nodes (N).Kind is
         when K_Lit =>
            Ignore := Plan_Emit (Steps, Count, O_Char, Nodes (N).Ch, -1, 0, 0);
         when K_Any =>
            Ignore := Plan_Emit (Steps, Count, O_Any, 0, -1, 0, 0);
         when K_Class =>
            Ignore := Plan_Emit (Steps, Count, O_Class, 0, N, 0, 0);
         when K_Grp =>
            Plan_Compile (Steps, Count, Nodes (N).Body_Node);
         when K_Cat =>
            for I in 0 .. Nodes (N).Kids_Count - 1 loop
               Plan_Compile (Steps, Count, Kid_Pool (Nodes (N).Kids_Start + I));
            end loop;
         when K_Alt =>
            for I in 0 .. Nodes (N).Kids_Count - 1 loop
               if I + 1 < Nodes (N).Kids_Count then
                  Sp := Plan_Emit (Steps, Count, O_Split, 0, -1, 0, 0);
                  Steps (Sp).X := Count;
                  Plan_Compile
                    (Steps, Count, Kid_Pool (Nodes (N).Kids_Start + I));
                  Jmps (NJmp) := Plan_Emit (Steps, Count, O_Jmp, 0, -1, 0, 0);
                  NJmp := NJmp + 1;
                  Steps (Sp).Y := Count;
               else
                  Plan_Compile
                    (Steps, Count, Kid_Pool (Nodes (N).Kids_Start + I));
               end if;
            end loop;
            for I in 0 .. NJmp - 1 loop
               Steps (Jmps (I)).X := Count;
            end loop;
         when K_Cnt =>
            for I in 1 .. Nodes (N).Least loop
               Plan_Compile (Steps, Count, Nodes (N).Body_Node);
            end loop;
            if Nodes (N).Unbounded then
               Sp := Plan_Emit (Steps, Count, O_Split, 0, -1, 0, 0);
               Steps (Sp).X := Count;
               Plan_Compile (Steps, Count, Nodes (N).Body_Node);
               Ignore := Plan_Emit (Steps, Count, O_Jmp, 0, -1, Sp, 0);
               Steps (Sp).Y := Count;
            else
               for I in 1 .. Nodes (N).Most - Nodes (N).Least loop
                  Sp := Plan_Emit (Steps, Count, O_Split, 0, -1, 0, 0);
                  Steps (Sp).X := Count;
                  Splits (NSplit) := Sp;
                  NSplit := NSplit + 1;
                  Plan_Compile (Steps, Count, Nodes (N).Body_Node);
               end loop;
               for I in 0 .. NSplit - 1 loop
                  Steps (Splits (I)).Y := Count;
               end loop;
            end if;
         when K_Rep =>
            if Nodes (N).Again = '?' then
               Sp := Plan_Emit (Steps, Count, O_Split, 0, -1, 0, 0);
               Steps (Sp).X := Count;
               Plan_Compile (Steps, Count, Nodes (N).Body_Node);
               Steps (Sp).Y := Count;
            elsif Nodes (N).Again = '*' then
               Sp := Plan_Emit (Steps, Count, O_Split, 0, -1, 0, 0);
               Steps (Sp).X := Count;
               Plan_Compile (Steps, Count, Nodes (N).Body_Node);
               Ignore := Plan_Emit (Steps, Count, O_Jmp, 0, -1, Sp, 0);
               Steps (Sp).Y := Count;
            elsif Nodes (N).Again = '+' then
               Start := Count;
               Plan_Compile (Steps, Count, Nodes (N).Body_Node);
               Sp := Plan_Emit (Steps, Count, O_Split, 0, -1, Start, 0);
               Steps (Sp).Y := Count;
            end if;
         when K_Ref =>
            -- A capture reference contributes nothing to the sweep plan.
            null;
      end case;
   end Plan_Compile;

   function Plan_Build (N : Natural) return Natural is
      Steps  : Step_Array_Access;
      Count  : Natural := 0;
      Ignore : Integer;
   begin
      if Plans (N).Steps /= null then
         return N;
      end if;
      Steps := new Step_Array;
      Plan_Compile (Steps, Count, N);
      Ignore := Plan_Emit (Steps, Count, O_Match, 0, -1, 0, 0);
      Plans (N) := (Steps => Steps, Count => Count);
      return N;
   end Plan_Build;

   function Step_Admits (S : Step_Type; B : Integer) return Boolean is
   begin
      case S.Op is
         when O_Char =>
            return S.Ch = B;
         when O_Any =>
            return True;
         when O_Class =>
            return Nodes (S.Class_Node).Members (B)
                     /= Nodes (S.Class_Node).Neg;
         when others =>
            return False;
      end case;
   end Step_Admits;

   procedure Add_Step
     (P : Plan_Record; Live : in out Index_Array; NLive : in out Natural;
      Seen : in out Seen_Array; Pc : Integer)
   is
   begin
      if Pc < 0 or else Pc >= P.Count or else Seen (Pc) then
         return;
      end if;
      Seen (Pc) := True;
      case P.Steps (Pc).Op is
         when O_Jmp =>
            Add_Step (P, Live, NLive, Seen, P.Steps (Pc).X);
         when O_Split =>
            Add_Step (P, Live, NLive, Seen, P.Steps (Pc).X);
            Add_Step (P, Live, NLive, Seen, P.Steps (Pc).Y);
         when others =>
            Live (NLive) := Pc;
            NLive := NLive + 1;
      end case;
   end Add_Step;

   function List_At_Match
     (P : Plan_Record; Live : Index_Array; NLive : Natural) return Boolean is
   begin
      for I in 0 .. NLive - 1 loop
         if P.Steps (Live (I)).Op = O_Match then
            return True;
         end if;
      end loop;
      return False;
   end List_At_Match;

   -- Every position the subtree can stop at, gathered in one sweep.
   procedure Plan_Stop_Points
     (Idx : Natural; Start : Integer; Ends : Stop_Array_Access;
      N_Ends : out Natural)
   is
      P     : constant Plan_Record := Plans (Idx);
      Cur   : Index_Array;
      Nxt   : Index_Array;
      NCur  : Natural := 0;
      NNxt  : Natural;
      Seen  : Seen_Array := (others => False);
   begin
      N_Ends := 0;
      Add_Step (P, Cur, NCur, Seen, 0);
      if List_At_Match (P, Cur, NCur) then
         Ends (N_Ends) := Start;
         N_Ends := N_Ends + 1;
      end if;
      for I in Start .. Subject_Len - 1 loop
         NNxt := 0;
         Seen := (others => False);
         for J in 0 .. NCur - 1 loop
            if Step_Admits (P.Steps (Cur (J)),
                            Character'Pos (Subject (I + 1)))
            then
               Add_Step (P, Nxt, NNxt, Seen, Cur (J) + 1);
            end if;
         end loop;
         Cur := Nxt;
         NCur := NNxt;
         if List_At_Match (P, Cur, NCur) then
            Ends (N_Ends) := I + 1;
            N_Ends := N_Ends + 1;
         end if;
         exit when NCur = 0;
      end loop;
   end Plan_Stop_Points;

   function Plan_Admits_All (Idx : Natural) return Boolean is
      P    : constant Plan_Record := Plans (Idx);
      Cur  : Index_Array;
      Nxt  : Index_Array;
      NCur : Natural := 0;
      NNxt : Natural;
      Seen : Seen_Array := (others => False);
   begin
      Add_Step (P, Cur, NCur, Seen, 0);
      for I in 0 .. Subject_Len - 1 loop
         NNxt := 0;
         Seen := (others => False);
         for J in 0 .. NCur - 1 loop
            if Step_Admits (P.Steps (Cur (J)),
                            Character'Pos (Subject (I + 1)))
            then
               Add_Step (P, Nxt, NNxt, Seen, Cur (J) + 1);
            end if;
         end loop;
         Cur := Nxt;
         NCur := NNxt;
      end loop;
      return List_At_Match (P, Cur, NCur);
   end Plan_Admits_All;

   -- ---- admission search ----
   --
   -- The walk is written in continuation-passing form. Each pending
   -- continuation is a resume point naming its shape, so that the rest of the
   -- walk can pick up where it left off once a node has been covered.

   function Admit_Seq
     (Cat : Natural; I : Natural; Pos : Integer; Caps : Caps_Array;
      K : Resume_Access) return Boolean
   is
      P : aliased Resume_Point;
   begin
      if I = Nodes (Cat).Kids_Count then
         return Resume (K, Pos, Caps);
      end if;
      P := (Kind => R_Seq, Node => Cat, Step => I, From => 0, Next => K);
      return Admit_Node
        (Kid_Pool (Nodes (Cat).Kids_Start + I), Pos, Caps, P'Unchecked_Access);
   end Admit_Seq;

   function Resume
     (K : Resume_Access; Pos : Integer; Caps : Caps_Array) return Boolean
   is
      Next : Caps_Array;
      Idx  : Natural;
   begin
      case K.Kind is
         when R_Done =>
            return Pos = Subject_Len;
         when R_Seq =>
            return Admit_Seq (K.Node, K.Step + 1, Pos, Caps, K.Next);
         when R_Star =>
            if Pos > K.From then
               return Admit_Star (K.Node, Pos, Caps, K.Next);
            end if;
            return False;
         when R_Plus =>
            return Admit_Star (K.Node, Pos, Caps, K.Next);
         when R_Cnt =>
            return Admit_Counted (K.Node, K.Step - 1, Pos, Caps, K.Next);
         when R_COpt =>
            if Pos > K.From then
               return Admit_Counted_Opt (K.Node, K.Step - 1, Pos, Caps, K.Next);
            end if;
            return False;
         when R_Grp =>
            Idx := K.Step;
            if Idx > Groups or else Idx > Max_Groups then
               return False;
            end if;
            Next := Caps;
            Next (2 * Idx) := K.From;
            Next (2 * Idx + 1) := Pos;
            return Resume (K.Next, Pos, Next);
      end case;
   end Resume;

   function Admit_Star
     (Body_Node : Natural; Pos : Integer; Caps : Caps_Array; K : Resume_Access)
      return Boolean
   is
      P : aliased Resume_Point;
   begin
      P := (Kind => R_Star, Node => Body_Node, Step => 0, From => Pos,
            Next => K);
      if Admit_Node (Body_Node, Pos, Caps, P'Unchecked_Access) then
         return True;
      end if;
      return Resume (K, Pos, Caps);
   end Admit_Star;

   function Admit_Counted
     (N : Natural; Remaining : Integer; Pos : Integer; Caps : Caps_Array;
      K : Resume_Access) return Boolean
   is
      P : aliased Resume_Point;
   begin
      if Remaining > 0 then
         P := (Kind => R_Cnt, Node => N, Step => Remaining, From => 0,
               Next => K);
         return Admit_Node
           (Nodes (N).Body_Node, Pos, Caps, P'Unchecked_Access);
      end if;
      if Nodes (N).Unbounded then
         return Admit_Star (Nodes (N).Body_Node, Pos, Caps, K);
      end if;
      return Admit_Counted_Opt
        (N, Nodes (N).Most - Nodes (N).Least, Pos, Caps, K);
   end Admit_Counted;

   function Admit_Counted_Opt
     (N : Natural; Opt : Integer; Pos : Integer; Caps : Caps_Array;
      K : Resume_Access) return Boolean
   is
      P : aliased Resume_Point;
   begin
      if Opt <= 0 then
         return Resume (K, Pos, Caps);
      end if;
      P := (Kind => R_COpt, Node => N, Step => Opt, From => Pos, Next => K);
      if Admit_Node (Nodes (N).Body_Node, Pos, Caps, P'Unchecked_Access) then
         return True;
      end if;
      return Resume (K, Pos, Caps);
   end Admit_Counted_Opt;

   function Admit_Node
     (N : Natural; Pos : Integer; Caps : Caps_Array; K : Resume_Access)
      return Boolean
   is
      P      : aliased Resume_Point;
      Idx    : Natural;
      From   : Integer;
      Width  : Integer;
      Member : Boolean;
      Ends   : Stop_Array_Access;
      N_Ends : Natural;
      Plan_Idx : Natural;
      Next_Caps : Caps_Array;
   begin
      -- A referenced group still needs its span recorded, but the span itself
      -- can be enumerated in one sweep whenever the group body holds no capture
      -- that is read back later.
      if Nodes (N).Kind = K_Grp and then Nodes (N).Idx <= 9
        and then Ref_Slots (Nodes (N).Idx)
        and then Slot_Free (Nodes (N).Body_Node)
      then
         Idx := Nodes (N).Idx;
         if Idx > Groups or else Idx > Max_Groups then
            return False;
         end if;
         Plan_Idx := Plan_Build (Nodes (N).Body_Node);
         Ends := new Stop_Array;
         Plan_Stop_Points (Plan_Idx, Pos, Ends, N_Ends);
         for J in 0 .. N_Ends - 1 loop
            Next_Caps := Caps;
            Next_Caps (2 * Idx) := Pos;
            Next_Caps (2 * Idx + 1) := Ends (J);
            if Resume (K, Ends (J), Next_Caps) then
               return True;
            end if;
         end loop;
         return False;
      end if;
      if Slot_Free (N) then
         Plan_Idx := Plan_Build (N);
         Ends := new Stop_Array;
         Plan_Stop_Points (Plan_Idx, Pos, Ends, N_Ends);
         for J in 0 .. N_Ends - 1 loop
            if Resume (K, Ends (J), Caps) then
               return True;
            end if;
         end loop;
         return False;
      end if;

      case Nodes (N).Kind is
         when K_Lit =>
            if Pos < Subject_Len
              and then Character'Pos (Subject (Pos + 1)) = Nodes (N).Ch
            then
               return Resume (K, Pos + 1, Caps);
            end if;
            return False;
         when K_Any =>
            if Pos < Subject_Len then
               return Resume (K, Pos + 1, Caps);
            end if;
            return False;
         when K_Class =>
            if Pos < Subject_Len then
               Member := Nodes (N).Members
                 (Character'Pos (Subject (Pos + 1)));
               if Member /= Nodes (N).Neg then
                  return Resume (K, Pos + 1, Caps);
               end if;
            end if;
            return False;
         when K_Cat =>
            return Admit_Seq (N, 0, Pos, Caps, K);
         when K_Alt =>
            for I in 0 .. Nodes (N).Kids_Count - 1 loop
               if Admit_Node
                 (Kid_Pool (Nodes (N).Kids_Start + I), Pos, Caps, K)
               then
                  return True;
               end if;
            end loop;
            return False;
         when K_Grp =>
            P := (Kind => R_Grp, Node => N, Step => Nodes (N).Idx,
                  From => Pos, Next => K);
            return Admit_Node
              (Nodes (N).Body_Node, Pos, Caps, P'Unchecked_Access);
         when K_Ref =>
            Idx := Nodes (N).Idx;
            if Idx > Groups or else Idx > Max_Groups then
               return False;
            end if;
            From := Caps (2 * Idx);
            if From < 0 then
               return False;
            end if;
            Width := Caps (2 * Idx + 1) - From;
            if Pos + Width > Subject_Len then
               return False;
            end if;
            for I in 0 .. Width - 1 loop
               if Subject (Pos + I + 1) /= Subject (From + I + 1) then
                  return False;
               end if;
            end loop;
            return Resume (K, Pos + Width, Caps);
         when K_Cnt =>
            return Admit_Counted (N, Nodes (N).Least, Pos, Caps, K);
         when K_Rep =>
            if Nodes (N).Again = '?' then
               if Admit_Node (Nodes (N).Body_Node, Pos, Caps, K) then
                  return True;
               end if;
               return Resume (K, Pos, Caps);
            end if;
            if Nodes (N).Again = '*' then
               return Admit_Star (Nodes (N).Body_Node, Pos, Caps, K);
            end if;
            if Nodes (N).Again = '+' then
               P := (Kind => R_Plus, Node => Nodes (N).Body_Node, Step => 0,
                     From => 0, Next => K);
               return Admit_Node
                 (Nodes (N).Body_Node, Pos, Caps, P'Unchecked_Access);
            end if;
            return False;
      end case;
   end Admit_Node;

   -- ---- public surface ----

   function Compile_Rule (Rule : String) return Boolean is
   begin
      Node_Count := 0;
      Kid_Used := 0;
      Groups := 0;
      Ok := True;
      if Rule'Length > Src'Length then
         return False;
      end if;
      Src_Len := Rule'Length;
      Src (1 .. Src_Len) := Rule;
      Src_Pos := 0;
      Root := Read_Alt;
      return Ok and then Src_Pos = Src_Len;
   end Compile_Rule;

   function Rule_Admits (Channel : String) return Boolean is
      Caps : Caps_Array := (others => -1);
      Done : aliased Resume_Point;
   begin
      if Channel'Length > Subject'Length then
         return False;
      end if;
      Subject_Len := Channel'Length;
      Subject (1 .. Subject_Len) := Channel;
      Ref_Slots := (others => False);
      Free_Cache := (others => -1);
      Plans := (others => (Steps => null, Count => 0));
      Collect_Referenced (Root);
      if Slot_Free (Root) then
         return Plan_Admits_All (Plan_Build (Root));
      end if;
      Done := (Kind => R_Done, Node => 0, Step => 0, From => 0, Next => null);
      return Admit_Node (Root, 0, Caps, Done'Unchecked_Access);
   end Rule_Admits;

end Admission_Rules;
