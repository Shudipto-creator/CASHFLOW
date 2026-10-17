import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const Navbar = () => {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <nav className="bg-primary text-white shadow-lg">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="text-xl font-bold">
            CFOne
          </Link>

          {isAuthenticated && (
            <div className="flex items-center space-x-6">
              <Link to="/dashboard" className="hover:text-blue-200">
                Dashboard
              </Link>
              <Link to="/documents" className="hover:text-blue-200">
                Documents
              </Link>
              <Link to="/analysis" className="hover:text-blue-200">
                Analysis
              </Link>

              <div className="flex items-center space-x-4">
                <span className="text-sm">{user?.email}</span>
                <button
                  onClick={handleLogout}
                  className="bg-white text-primary px-4 py-2 rounded hover:bg-blue-100"
                >
                  Logout
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
