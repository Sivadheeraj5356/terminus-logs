import java.sql.*;
public final class DbInspector {
  public static void main(String[] args) throws Exception {
    if(args.length!=2) throw new IllegalArgumentException("db sql");
    Class.forName("org.duckdb.DuckDBDriver");
    try(Connection c=DriverManager.getConnection("jdbc:duckdb:"+args[0]); Statement s=c.createStatement(); ResultSet r=s.executeQuery(args[1])){
      ResultSetMetaData m=r.getMetaData(); int n=m.getColumnCount();
      while(r.next()){
        for(int i=1;i<=n;i++){if(i>1)System.out.print('\u001f');Object v=r.getObject(i);if(v==null)System.out.print("\\N");else{String x=v.toString().replace("\\","\\\\").replace("\n","\\n").replace("\u001f","\\u001f");System.out.print(x);}}
        System.out.println();
      }
    }
  }
}
