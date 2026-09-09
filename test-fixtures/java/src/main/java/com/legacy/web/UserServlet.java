package com.legacy.web;

import com.legacy.dao.UserDAO;
import com.legacy.model.User;

import javax.servlet.RequestDispatcher;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.sql.SQLException;
import java.util.List;

public class UserServlet extends HttpServlet {
    private static final long serialVersionUID = 1L;
    private UserDAO userDAO;

    public void init() {
        userDAO = new UserDAO();
    }

    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        String action = request.getParameter("action");
        if (action == null) {
            action = "list";
        }

        try {
            switch (action) {
                case "delete":
                    deleteUser(request, response);
                    break;
                case "list":
                default:
                    listUsers(request, response);
                    break;
            }
        } catch (SQLException ex) {
            throw new ServletException(ex);
        }
    }

    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        String name = request.getParameter("name");
        String email = request.getParameter("email");
        String department = request.getParameter("department");

        User newUser = new User(0, name, email, department, null);
        try {
            userDAO.insertUser(newUser);
            response.sendRedirect(request.getContextPath() + "/users?action=list");
        } catch (SQLException ex) {
            throw new ServletException(ex);
        }
    }

    private void listUsers(HttpServletRequest request, HttpServletResponse response)
            throws SQLException, IOException, ServletException {
        List<User> listUsers = userDAO.listAllUsers();
        request.setAttribute("listUsers", listUsers);
        RequestDispatcher dispatcher = request.getRequestDispatcher("index.jsp");
        dispatcher.forward(request, response);
    }

    private void deleteUser(HttpServletRequest request, HttpServletResponse response)
            throws SQLException, IOException {
        int id = Integer.parseInt(request.getParameter("id"));
        userDAO.deleteUser(id);
        response.sendRedirect(request.getContextPath() + "/users?action=list");
    }
}
