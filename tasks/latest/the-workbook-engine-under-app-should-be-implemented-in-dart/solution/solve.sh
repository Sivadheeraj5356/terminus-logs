#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app/src /app/output
cat > /app/src/main.dart <<'DART'
import 'dart:convert';
import 'dart:io';

final cellToken = RegExp(r'([A-Za-z_][A-Za-z0-9_]*![A-Z]+\d+(?::[A-Z]+\d+)?|[A-Z]+\d+(?::[A-Z]+\d+)?|[A-Za-z_][A-Za-z0-9_]*)');
final funcs = {'IF', 'SUM', 'MIN', 'MAX', 'COUNT'};

int colNum(String s) { var c = 0; for (var u in s.codeUnits) { c = c * 26 + u - 64; } return c; }
String colName(int c) { var s = ''; while (c > 0) { var r = (c - 1) % 26; s = String.fromCharCode(65 + r) + s; c = (c - 1) ~/ 26; } return s; }
List<int> rc(String a) { var m = RegExp(r'([A-Z]+)(\d+)').firstMatch(a)!; return [int.parse(m.group(2)!), colNum(m.group(1)!)]; }
List<String> cellsRange(String a, String b) {
  var x = rc(a), y = rc(b), out = <String>[];
  for (var r = x[0] < y[0] ? x[0] : y[0]; r <= (x[0] > y[0] ? x[0] : y[0]); r++) {
    for (var c = x[1] < y[1] ? x[1] : y[1]; c <= (x[1] > y[1] ? x[1] : y[1]); c++) { out.add('${colName(c)}$r'); }
  }
  return out;
}

class Parser {
  String s; int i = 0;
  Parser(this.s);
  void ws() { while (i < s.length && s.codeUnitAt(i) <= 32) i++; }
  bool eat(String t) { ws(); if (s.startsWith(t, i)) { i += t.length; return true; } return false; }
  dynamic parse() { var v = cmp(); ws(); if (i != s.length) throw Exception('tail'); return v; }
  dynamic cmp() { var a = add(); for (var op in ['>=','<=','==','=','>','<']) { if (eat(op)) { var b = add(); if (op == '>=') return a >= b; if (op == '<=') return a <= b; if (op == '>' ) return a > b; if (op == '<') return a < b; return a == b; } } return a; }
  dynamic add() { var a = mul(); while (true) { if (eat('+')) { var b = mul(); a = (a is int && b is int) ? a + b : (a as num) + (b as num); } else if (eat('-')) { var b = mul(); a = (a is int && b is int) ? a - b : (a as num) - (b as num); } else { return a; } } }
  dynamic mul() { var a = unary(); while (true) { if (eat('*')) { var b = unary(); a = (a is int && b is int) ? a * b : (a as num) * (b as num); } else if (eat('/')) { var b = unary(); if ((b as num) == 0) throw IntegerDivisionByZeroException(); a = (a as num) / b; } else { return a; } } }
  dynamic unary() { ws(); if (eat('-')) { var v = unary(); return v is int ? -v : -(v as num); } if (eat('+')) return unary(); if (eat('(')) { var v = cmp(); if (!eat(')')) throw Exception('paren'); return v; } return number(); }
  dynamic number() { ws(); var st = i; while (i < s.length && RegExp(r'[0-9.]').hasMatch(s[i])) i++; if (st == i) throw Exception('num'); var t = s.substring(st, i); return t.contains('.') ? double.parse(t) : int.parse(t); }
}

bool truthy(dynamic v) { if (v is bool) return v; if (v is num) return v != 0; return v != null; }
String valStr(dynamic v) { return v.toString(); }

Map<String, dynamic> solve(String path) {
  var wb = jsonDecode(File(path).readAsStringSync()) as Map<String, dynamic>;
  var cells = <String, dynamic>{};
  var formulas = <String, String>{};
  var names = Map<String, dynamic>.from(wb['names'] ?? {});
  for (var sh in (wb['sheets'] as List)) {
    var sm = sh as Map<String, dynamic>; var sn = sm['name'] as String;
    (sm['cells'] as Map<String, dynamic>).forEach((c, v) { var id = '$sn!$c'; cells[id] = v; if (v is String && v.startsWith('=')) formulas[id] = v; });
  }
  List<String> expand(String tok, String cur) {
    tok = (names[tok] ?? tok).toString(); var sh = cur, addr = tok;
    if (tok.contains('!')) { var p = tok.split('!'); sh = p[0]; addr = p.sublist(1).join('!'); }
    if (addr.contains(':')) { var p = addr.split(':'); return cellsRange(p[0], p[1]).map((x) => '$sh!$x').toList(); }
    return ['$sh!$addr'];
  }
  var deps = <String, List<String>>{};
  for (var ent in formulas.entries) {
    var cur = ent.key.split('!')[0]; var ds = <String>[];
    for (var m in cellToken.allMatches(ent.value.substring(1))) {
      var t = m.group(1)!; if (funcs.contains(t.toUpperCase())) continue;
      if (RegExp(r'^[A-Za-z_]').hasMatch(t) && !names.containsKey(t) && !RegExp(r'[A-Z]+\d+').hasMatch(t)) continue;
      ds.addAll(expand(t, cur));
    }
    deps[ent.key] = ds.toSet().toList()..sort();
  }
  var visiting = <String>{}, done = <String>{}, cycles = <String>{}; var order = <String>[];
  void dfs(String n, List<String> st) {
    if (done.contains(n)) return;
    if (visiting.contains(n)) { cycles.addAll(st.sublist(st.indexOf(n))); return; }
    visiting.add(n);
    for (var d in deps[n] ?? const <String>[]) { if (formulas.containsKey(d)) dfs(d, [...st, d]); }
    visiting.remove(n); done.add(n); order.add(n);
  }
  for (var n in (formulas.keys.toList()..sort())) { dfs(n, [n]); }
  order = order.where((x) => !cycles.contains(x)).toList();

  Map<String, dynamic> evalAll(Map<String, dynamic> base) {
    var vals = <String, dynamic>{};
    var active = <String>{};
    late dynamic Function(String) val;
    late dynamic Function(String, String) calc;
    late dynamic Function(String, String) simple;
    val = (String fid) {
      if (vals.containsKey(fid)) return vals[fid];
      if (active.contains(fid)) throw Exception('recursive');
      var raw = base[fid];
      if (cycles.contains(fid)) return vals[fid] = '#CYCLE';
      if (raw is num) return vals[fid] = raw;
      if (raw is! String || !raw.startsWith('=')) return vals[fid] = raw;
      try { active.add(fid); var out = calc(raw.substring(1), fid.split('!')[0]); active.remove(fid); return vals[fid] = out; }
      on IntegerDivisionByZeroException { active.remove(fid); return vals[fid] = '#DIV0'; }
      catch (_) { active.remove(fid); return vals[fid] = '#VALUE'; }
    };
    calc = (String expr, String cur) {
      while (true) {
        var m = RegExp(r'(SUM|MIN|MAX|COUNT)\(([^()]+)\)').firstMatch(expr); if (m == null) break;
        var vs = expand(m.group(2)!.trim(), cur).map((x) => val(x)).toList();
        var err = vs.cast<dynamic?>().firstWhere((x) => x is String && x.startsWith('#'), orElse: () => null);
        dynamic rep;
        if (err != null) rep = err; else if (m.group(1) == 'SUM') { num sum = 0; for (var v in vs) if (v is num) sum += v; rep = sum is int ? sum : (sum == sum.roundToDouble() ? sum.toInt() : sum); }
        else if (m.group(1) == 'COUNT') { rep = vs.whereType<num>().length; }
        else { var nums = vs.map((x) { if (x is! num) throw Exception('value'); return x; }).toList(); nums.sort(); rep = m.group(1) == 'MIN' ? nums.first : nums.last; }
        expr = expr.substring(0, m.start) + valStr(rep) + expr.substring(m.end);
      }
      var im = RegExp(r'^IF\((.*),(.*),(.*)\)$').firstMatch(expr);
      if (im != null) expr = truthy(simple(im.group(1)!, cur)) ? im.group(2)! : im.group(3)!;
      return simple(expr, cur);
    };
    simple = (String e, String cur) {
      var toks = cellToken.allMatches(e).map((m) => m.group(1)!).toSet().toList()..sort((a,b) => b.length.compareTo(a.length));
      for (var t in toks) {
        if (funcs.contains(t.toUpperCase())) continue;
        if (RegExp(r'^[A-Za-z_]').hasMatch(t) && !names.containsKey(t) && !RegExp(r'[A-Z]+\d+').hasMatch(t)) continue;
        var v = val(expand(t, cur).first); if (v is String && v.startsWith('#')) return v;
        e = e.replaceAll(t, valStr(v));
      }
      if (e.contains('/0')) throw IntegerDivisionByZeroException();
      return Parser(e).parse();
    };
    for (var k in (base.keys.toList()..sort())) { val(k); }
    return vals;
  }
  var cur = Map<String, dynamic>.from(cells); var finalVals = evalAll(cur); var rec = <Map<String, dynamic>>[];
  for (var ed in (wb['edits'] ?? []) as List) {
    var e = ed as Map<String, dynamic>; var before = finalVals; cur[e['cell']] = e['value']; if (e['value'] is String && (e['value'] as String).startsWith('=')) formulas[e['cell']] = e['value'];
    finalVals = evalAll(cur); var changed = finalVals.keys.where((k) => finalVals[k] != before[k]).toList()..sort(); var recomputed = finalVals.keys.toList()..sort();
    rec.add({'id': e['id'], 'changed': changed, 'recomputed': recomputed});
  }
  var errors = <Map<String, dynamic>>[]; for (var k in (finalVals.keys.toList()..sort())) { var v = finalVals[k]; if (v is String && v.startsWith('#')) errors.add({'cell': k, 'error': v}); }
  List<String> trans(String k) { var seen = <String>{}; var st = [...(deps[k] ?? const <String>[])]; while (st.isNotEmpty) { var x = st.removeLast(); if (seen.contains(x)) continue; if (formulas.containsKey(x)) { seen.add(x); st.addAll(deps[x] ?? const <String>[]); } } return seen.toList()..sort(); }
  var lineage = <Map<String, dynamic>>[]; for (var k in (formulas.keys.toList()..sort())) { lineage.add({'cell': k, 'direct': deps[k] ?? <String>[], 'transitive': trans(k)}); }
  var audit = <Map<String, dynamic>>[]; var checksum = 0; num nsum = 0; var textc = 0;
  for (var k in (formulas.keys.toList()..sort())) { var v = finalVals[k]; var state = v == '#CYCLE' ? 'cycle' : (v is String && v.startsWith('#')) ? 'error' : 'value'; audit.add({'cell': k, 'state': state, 'value': v}); if (v is num) nsum += v; if (v is String && !v.startsWith('#')) textc++; for (var u in '$k=$v'.codeUnits) { checksum = (checksum * 131 + u) % 1000000007; } }
  var values = <String, dynamic>{}; for (var k in (finalVals.keys.toList()..sort())) { values[k] = finalVals[k]; }
  var fkeys = formulas.keys.toList()..sort();
  return {
    'parse': {'sheets': (wb['sheets'] as List).length, 'cells': cells.length, 'formulas': formulas.length, 'names': names.length, 'edits': ((wb['edits'] ?? []) as List).length},
    'formulas': {'formulas': [for (var k in fkeys) {'cell': k, 'formula': formulas[k]}]},
    'deps': {'deps': [for (var k in fkeys) {'cell': k, 'depends_on': deps[k] ?? <String>[]}]},
    'order': {'order': order, 'cycles': (cycles.toList()..sort())},
    'values': {'values': values},
    'errors': {'errors': errors},
    'recalculation': {'edits': rec},
    'lineage': {'lineage': lineage},
    'audit': {'audit': audit},
    'metrics': {'max_direct_dependencies': fkeys.isEmpty ? 0 : fkeys.map((k) => (deps[k] ?? []).length).reduce((a,b)=>a>b?a:b), 'max_transitive_dependencies': lineage.isEmpty ? 0 : lineage.map((x) => (x['transitive'] as List).length).reduce((a,b)=>a>b?a:b), 'numeric_formula_sum': nsum, 'text_formula_count': textc, 'checksum': checksum},
    'summary': {'formulas': formulas.length, 'dependencies': deps.values.fold<int>(0, (a,b)=>a+b.length), 'cycles': cycles.length, 'errors': errors.length, 'edits': ((wb['edits'] ?? []) as List).length, 'lineage_edges': lineage.fold<int>(0, (a,b)=>a+(b['transitive'] as List).length)},
  };
}

void main(List<String> args) {
  if (args.length < 2) { exit(2); }
  var input = args[0], output = args[1];
  var out = Directory(output); out.createSync(recursive: true);
  var solved = solve(input);
  for (var e in solved.entries) { File('${out.path}/${e.key}.json').writeAsStringSync(jsonEncode(e.value) + '\n'); }
}
DART
dart /app/src/main.dart /app/data/workbook.json /app/output
