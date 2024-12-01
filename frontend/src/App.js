import React, { useState, useEffect } from 'react';
import './App.css';
import LoanTable from './components/LoanTable';
import Login from './components/Login';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Home from './pages/Home';

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

function App() {
  const [apiKey, setApiKey] = useState(localStorage.getItem('apiKey'));

  const handleLogin = (key) => {
    setApiKey(key);
  };

  const handleLogout = () => {
    localStorage.removeItem('apiKey');
    setApiKey(null);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div className="App">
        {!apiKey ? (
          <Login onLogin={handleLogin} />
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '1rem' }}>
              <button 
                onClick={handleLogout}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: '#f44336',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Logout
              </button>
            </div>
            <Home />
          </>
        )}
      </div>
    </ThemeProvider>
  );
}

export default App;
