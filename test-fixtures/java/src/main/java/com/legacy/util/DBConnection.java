package com.legacy.util;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

public class DBConnection {
    // Legacy hardcoded connection string (code smell to modernize into .env)
    private static final String URL = "jdbc:mysql://localhost:3306/legacy_company_db?useSSL=false";
    private static final String USER = "root";
    private static final String PASSWORD = "root_password";

    static {
        try {
            // Deprecated legacy driver name (smell for modernizer to update to modern connector)
            Class.forName("com.mysql.jdbc.Driver");
        } catch (ClassNotFoundException e) {
            e.printStackTrace();
        }
    }

    public static Connection getConnection() throws SQLException {
        return DriverManager.getConnection(URL, USER, PASSWORD);
    }
}
