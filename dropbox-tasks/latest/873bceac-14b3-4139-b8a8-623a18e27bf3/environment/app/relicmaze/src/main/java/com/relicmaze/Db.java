package com.relicmaze;

import java.io.FileInputStream;
import java.io.InputStream;
import java.math.BigDecimal;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Properties;

/**
 * Loads the live RelicMaze dataset from PostgreSQL over JDBC. Connection
 * settings come from a properties file (default {@code /app/relicmaze/db.properties},
 * overridable with the {@code RELICMAZE_DB_PROPERTIES} environment variable).
 */
public final class Db {

    private Db() {
    }

    public static Properties loadProperties() throws Exception {
        String path = System.getenv("RELICMAZE_DB_PROPERTIES");
        if (path == null || path.isEmpty()) {
            path = "/app/relicmaze/db.properties";
        }
        Properties props = new Properties();
        try (InputStream in = new FileInputStream(path)) {
            props.load(in);
        }
        return props;
    }

    public static World loadWorld() throws Exception {
        return loadWorld(loadProperties());
    }

    public static World loadWorld(Properties props) throws Exception {
        String host = props.getProperty("host", "localhost");
        String port = props.getProperty("port", "5432");
        String database = props.getProperty("database", "relicmaze");
        String user = props.getProperty("user", "relickeeper");
        String password = props.getProperty("password", "");
        String url = "jdbc:postgresql://" + host + ":" + port + "/" + database;

        Map<String, Room> rooms = new LinkedHashMap<>();
        Map<String, Relic> relics = new LinkedHashMap<>();
        List<Passage> passages = new ArrayList<>();

        try (Connection conn = DriverManager.getConnection(url, user, password);
             Statement st = conn.createStatement()) {

            try (ResultSet rs = st.executeQuery(
                    "SELECT room_id, name, biome, base_light, locked, unlock_relic FROM rooms")) {
                while (rs.next()) {
                    rooms.put(rs.getString("room_id"), new Room(
                            rs.getString("room_id"),
                            rs.getString("name"),
                            rs.getString("biome"),
                            rs.getInt("base_light"),
                            rs.getBoolean("locked"),
                            rs.getString("unlock_relic")));
                }
            }

            try (ResultSet rs = st.executeQuery(
                    "SELECT relic_id, name, room_id, rarity, mass_g, discovered_at, cursed, luminosity FROM relics")) {
                while (rs.next()) {
                    OffsetDateTime odt = rs.getObject("discovered_at", OffsetDateTime.class);
                    Instant discovered = odt.toInstant();
                    relics.put(rs.getString("relic_id"), new Relic(
                            rs.getString("relic_id"),
                            rs.getString("name"),
                            rs.getString("room_id"),
                            rs.getString("rarity"),
                            rs.getInt("mass_g"),
                            discovered,
                            rs.getBoolean("cursed"),
                            rs.getBigDecimal("luminosity")));
                }
            }

            try (ResultSet rs = st.executeQuery(
                    "SELECT from_room, to_room, direction, torch_cost FROM passages")) {
                while (rs.next()) {
                    passages.add(new Passage(
                            rs.getString("from_room"),
                            rs.getString("to_room"),
                            rs.getString("direction"),
                            rs.getBigDecimal("torch_cost")));
                }
            }
        }

        return new World(rooms, relics, passages);
    }
}
