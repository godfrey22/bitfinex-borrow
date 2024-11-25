import React, { useState, useEffect, useRef } from 'react';
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
  CircularProgress,
  Alert
} from '@mui/material';

const LoanTable = () => {
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);
  const requestCounter = useRef(0);
  
  const fetchLoans = async (retryCount = 0) => {
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 2000;
    const currentRequest = ++requestCounter.current;

    if (!mountedRef.current) {
      console.log(`[${currentRequest}] Component unmounted, aborting fetch`);
      return;
    }

    try {
      console.log(`[${currentRequest}] Fetching loans...`);
      const response = await fetch('http://localhost:8000/api/loans', {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        if (response.status === 503 && retryCount < MAX_RETRIES) {
          console.log(`[${currentRequest}] Service unavailable, retrying...`);
          await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
          return fetchLoans(retryCount + 1);
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log(`[${currentRequest}] Received data:`, {
        dataLength: data.length,
        firstLoanId: data[0]?.loan_id
      });
      
      if (mountedRef.current) {
        setLoans(data);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      console.error(`[${currentRequest}] Error:`, err);
      if (mountedRef.current) {
        setError(err.message);
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    console.log('Component mounted');
    mountedRef.current = true;

    const fetchData = async () => {
      if (mountedRef.current) {
        await fetchLoans();
      }
    };

    fetchData();

    const interval = setInterval(() => {
      if (mountedRef.current) {
        fetchData();
      }
    }, 30000);

    return () => {
      console.log('Component will unmount');
      mountedRef.current = false;
      clearInterval(interval);
    };
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
        <Alert severity="error">Error loading loans: {error}</Alert>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        Active Loans ({loans.length})
      </Typography>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Symbol</TableCell>
              <TableCell>Amount</TableCell>
              <TableCell>Rate</TableCell>
              <TableCell>Period (Days)</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loans.map((loan) => (
              <TableRow key={loan.loan_id || loan.credit_id}>
                <TableCell>{loan.loan_id || loan.credit_id}</TableCell>
                <TableCell>{loan.symbol}</TableCell>
                <TableCell>{loan.amount.toFixed(2)}</TableCell>
                <TableCell>{loan.rate.toFixed(6)}</TableCell>
                <TableCell>{loan.period_days}</TableCell>
                <TableCell>{loan.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default LoanTable; 