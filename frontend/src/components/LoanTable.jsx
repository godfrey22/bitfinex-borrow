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
  Alert,
  TextField,
  Button,
  Checkbox,
  Stack
} from '@mui/material';

const LoanTable = () => {
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rateFilter, setRateFilter] = useState('');
  const [selectedLoans, setSelectedLoans] = useState([]);
  const [closingLoans, setClosingLoans] = useState(false);
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

  const handleRateFilterChange = (event) => {
    setRateFilter(event.target.value);
  };

  const filteredLoans = rateFilter
    ? loans.filter(loan => loan.rate >= parseFloat(rateFilter))
    : loans;

  const handleSelectAll = () => {
    if (selectedLoans.length === filteredLoans.length) {
      setSelectedLoans([]);
    } else {
      setSelectedLoans(filteredLoans.map(loan => loan.loan_id || loan.credit_id));
    }
  };

  const handleSelectLoan = (loanId) => {
    setSelectedLoans(prev => 
      prev.includes(loanId)
        ? prev.filter(id => id !== loanId)
        : [...prev, loanId]
    );
  };

  const handleCloseLoans = async () => {
    if (!selectedLoans.length) return;

    try {
      setClosingLoans(true);
      console.log('Attempting to close loans:', selectedLoans);
      
      const response = await fetch('http://localhost:8000/api/loans/close', {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          loan_ids: selectedLoans  // Wrap in object with loan_ids key
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to close loans: ${response.status}`);
      }

      const result = await response.json();
      console.log('Close result:', result);

      if (result.success) {
        // Show success message
        setError(null);
        // Refresh loans list
        await fetchLoans();
        setSelectedLoans([]);
      } else {
        throw new Error('Failed to close some loans');
      }
    } catch (err) {
      console.error('Error closing loans:', err);
      setError(err.message);
    } finally {
      setClosingLoans(false);
    }
  };

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
        Active Loans ({filteredLoans.length})
      </Typography>

      <Stack direction="row" spacing={2} mb={2} alignItems="center">
        <TextField
          label="Minimum Rate Filter"
          type="number"
          value={rateFilter}
          onChange={handleRateFilterChange}
          size="small"
          inputProps={{ step: "0.000001" }}
        />
        <Button
          variant="contained"
          onClick={handleSelectAll}
          disabled={!filteredLoans.length}
        >
          {selectedLoans.length === filteredLoans.length ? 'Deselect All' : 'Select All'}
        </Button>
        <Button
          variant="contained"
          color="secondary"
          onClick={handleCloseLoans}
          disabled={!selectedLoans.length || closingLoans}
        >
          {closingLoans ? 'Closing...' : 'Close Selected'}
        </Button>
      </Stack>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  checked={selectedLoans.length === filteredLoans.length && filteredLoans.length > 0}
                  indeterminate={selectedLoans.length > 0 && selectedLoans.length < filteredLoans.length}
                  onChange={handleSelectAll}
                />
              </TableCell>
              <TableCell>ID</TableCell>
              <TableCell>Symbol</TableCell>
              <TableCell>Amount</TableCell>
              <TableCell>Rate</TableCell>
              <TableCell>Period (Days)</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredLoans.map((loan) => (
              <TableRow 
                key={loan.loan_id || loan.credit_id}
                selected={selectedLoans.includes(loan.loan_id || loan.credit_id)}
              >
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={selectedLoans.includes(loan.loan_id || loan.credit_id)}
                    onChange={() => handleSelectLoan(loan.loan_id || loan.credit_id)}
                  />
                </TableCell>
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