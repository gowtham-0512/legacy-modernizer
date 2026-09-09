package com.legacy.dao;

import com.legacy.model.User;
import com.legacy.util.DBConnection;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class UserDAO {

    public List<User> listAllUsers() throws SQLException {
        List<User> listUser = new ArrayList<>();
        String sql = "SELECT id, name, email, department, created_at FROM users ORDER BY id ASC";

        try (Connection connection = DBConnection.getConnection();
             Statement statement = connection.createStatement();
             ResultSet resultSet = statement.executeQuery(sql)) {

            while (resultSet.next()) {
                int id = resultSet.getInt("id");
                String name = resultSet.getString("name");
                String email = resultSet.getString("email");
                String department = resultSet.getString("department");
                Timestamp createdAt = resultSet.getTimestamp("created_at");

                listUser.add(new User(id, name, email, department, createdAt));
            }
        }
        return listUser;
    }

    public User getUserById(int id) throws SQLException {
        User user = null;
        String sql = "SELECT id, name, email, department, created_at FROM users WHERE id = ?";

        try (Connection connection = DBConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setInt(1, id);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    String name = resultSet.getString("name");
                    String email = resultSet.getString("email");
                    String department = resultSet.getString("department");
                    Timestamp createdAt = resultSet.getTimestamp("created_at");
                    user = new User(id, name, email, department, createdAt);
                }
            }
        }
        return user;
    }

    public boolean insertUser(User user) throws SQLException {
        String sql = "INSERT INTO users (name, email, department, created_at) VALUES (?, ?, ?, NOW())";
        try (Connection connection = DBConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, user.getName());
            statement.setString(2, user.getEmail());
            statement.setString(3, user.getDepartment());
            return statement.executeUpdate() > 0;
        }
    }

    public boolean deleteUser(int id) throws SQLException {
        String sql = "DELETE FROM users WHERE id = ?";
        try (Connection connection = DBConnection.getConnection();
             PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setInt(1, id);
            return statement.executeUpdate() > 0;
        }
    }
}
