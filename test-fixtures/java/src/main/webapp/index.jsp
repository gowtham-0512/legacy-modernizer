<%@ page language="java" contentType="text/html; charset=UTF-8" pageEncoding="UTF-8"%>
<%@ page import="java.util.List" %>
<%@ page import="com.legacy.model.User" %>
<!DOCTYPE html>
<html>
<head>
    <title>Legacy User Management System</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
        th { background-color: #f4f4f4; }
        .form-group { margin-bottom: 12px; }
        label { display: block; font-weight: bold; }
        input[type="text"], input[type="email"] { width: 300px; padding: 6px; }
        button { padding: 8px 16px; background-color: #0066cc; color: white; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <h1>User Directory (Legacy JSP MVC)</h1>
    
    <h3>Add New User</h3>
    <form action="users" method="post">
        <div class="form-group">
            <label>Full Name:</label>
            <input type="text" name="name" required />
        </div>
        <div class="form-group">
            <label>Email Address:</label>
            <input type="email" name="email" required />
        </div>
        <div class="form-group">
            <label>Department:</label>
            <input type="text" name="department" required />
        </div>
        <button type="submit">Save User</button>
    </form>

    <h3>Active Users</h3>
    <table>
        <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Email</th>
            <th>Department</th>
            <th>Created At</th>
            <th>Action</th>
        </tr>
        <%
            List<User> listUsers = (List<User>) request.getAttribute("listUsers");
            if (listUsers != null && !listUsers.isEmpty()) {
                for (User u : listUsers) {
        %>
        <tr>
            <td><%= u.getId() %></td>
            <td><%= u.getName() %></td>
            <td><%= u.getEmail() %></td>
            <td><%= u.getDepartment() %></td>
            <td><%= u.getCreatedAt() %></td>
            <td><a href="users?action=delete&id=<%= u.getId() %>" onclick="return confirm('Delete user?');">Delete</a></td>
        </tr>
        <%
                }
            } else {
        %>
        <tr>
            <td colspan="6">No users found. Add one above.</td>
        </tr>
        <%
            }
        %>
    </table>
</body>
</html>
