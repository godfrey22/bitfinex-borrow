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
    const RETRY_DELAY = 2000; // 2 seconds
    const currentRequest = ++requestCounter.current;

    console.log(`[${currentRequest}] Starting fetchLoans request (attempt ${retryCount + 1}/${MAX_RETRIES + 1})`, {
      isMounted: mountedRef.current,
      currentLoading: loading,
      currentLoansCount: loans.length
    });
    
    if (!mountedRef.current) {
      console.log(`[${currentRequest}] Component unmounted, aborting fetch`);
      return;
    }
    
    try {
      console.log(`[${currentRequest}] Fetching from API...`);
      const response = await fetch('http://localhost:8000/api/loans', {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        if (response.status === 503 && retryCount < MAX_RETRIES) {
          console.log(`[${currentRequest}] Service unavailable, retrying in ${RETRY_DELAY}ms... (attempt ${retryCount + 1}/${MAX_RETRIES})`);
          await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
          return fetchLoans(retryCount + 1);
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log(`[${currentRequest}] Received data:`, {
        dataLength: data.length,
        firstLoanId: data[0]?.loan_id,
        isMounted: mountedRef.current
      });
      
      if (!data || !data.length) {
        if (retryCount < MAX_RETRIES) {
          console.log(`[${currentRequest}] No loans data received, retrying in ${RETRY_DELAY}ms...`);
          await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
          return fetchLoans(retryCount + 1);
        }
        throw new Error('No loans data received after all retries');
      }
      
      if (mountedRef.current) {
        console.log(`[${currentRequest}] Updating state with ${data.length} loans`);
        setLoans(data);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      console.error(`[${currentRequest}] Error in fetchLoans:`, err);
      if (mountedRef.current) {
        console.log(`[${currentRequest}] Setting error state`);
        setError(err.message);
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    console.log('Effect triggered', {
      isFirstMount: mountedRef.current,
      currentLoansCount: loans.length
    });
    
    // Initial fetch
    fetchLoans();
    
    // Set up polling with retry mechanism
    console.log('Setting up polling interval');
    const interval = setInterval(() => {
      console.log('Polling interval triggered');
      fetchLoans();
    }, 30000);
    
    // Cleanup function
    return () => {
      console.log('Cleanup: Component unmounting');
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, []); // Empty dependency array

  console.log('Component rendering', {
    loading,
    errorPresent: !!error,
    loansCount: loans.length
  });

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
        Active Loans
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