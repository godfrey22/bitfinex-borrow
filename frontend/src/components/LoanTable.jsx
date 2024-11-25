import React, { useState, useEffect } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  Box,
  CircularProgress
} from '@mui/material';

const LoanTable = () => {
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchLoans = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/loans');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setLoans(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLoans();
    // Poll for updates every 30 seconds
    const interval = setInterval(fetchLoans, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={3}>
        <Typography color="error">Error: {error}</Typography>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        Active Loans
      </Typography>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Symbol</TableCell>
              <TableCell>Amount</TableCell>
              <TableCell>Rate (% APR)</TableCell>
              <TableCell>Period (Days)</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Daily Earnings</TableCell>
              <TableCell>Annual Earnings</TableCell>
              <TableCell>Auto Renew</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loans.map((loan) => (
              <TableRow key={loan.loan_id || loan.credit_id}>
                <TableCell>{loan.loan_id || loan.credit_id}</TableCell>
                <TableCell>{loan.symbol}</TableCell>
                <TableCell>{loan.amount.toFixed(2)}</TableCell>
                <TableCell>{loan.rate.toFixed(4)}%</TableCell>
                <TableCell>{loan.period_days}</TableCell>
                <TableCell>{loan.status}</TableCell>
                <TableCell>${loan.daily_earnings.toFixed(4)}</TableCell>
                <TableCell>${loan.annual_earnings.toFixed(2)}</TableCell>
                <TableCell>{loan.auto_renew ? 'Yes' : 'No'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default LoanTable; 