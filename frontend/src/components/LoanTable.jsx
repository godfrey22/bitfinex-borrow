import React, { useState, useEffect, useRef, useMemo } from 'react';
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
  Stack,
  Grid,
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';

const FUNDING_SYMBOLS = ['fUSD', 'fBTC', 'fETH', 'fUSDT'];

const FundingBook = ({ symbol }) => {
  const [book, setBook] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchBook = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/funding-book/${symbol}`, {
          headers: {
            'X-API-Key': localStorage.getItem('apiKey')
          }
        });
        if (!response.ok) {
          if (response.status === 403) {
            throw new Error('Unauthorized access');
          }
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setBook(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching funding book:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (symbol) {
      fetchBook();
    }
  }, [symbol]);

  if (loading) return <CircularProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!symbol) return <Typography>Select a symbol to view funding book</Typography>;

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Funding Book (Lenders) - {symbol}
      </Typography>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Rate (%)</TableCell>
              <TableCell>Period (Days)</TableCell>
              <TableCell>Count</TableCell>
              <TableCell>Amount</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {book.map((entry, index) => (
              <TableRow key={index}>
                <TableCell>{entry.rate.toFixed(6)}%</TableCell>
                <TableCell>{entry.period}</TableCell>
                <TableCell>{entry.count}</TableCell>
                <TableCell>{entry.amount.toFixed(2)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

const LoanTable = () => {
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rateFilter, setRateFilter] = useState('');
  const [selectedLoans, setSelectedLoans] = useState([]);
  const [closingLoans, setClosingLoans] = useState(false);
  const mountedRef = useRef(true);
  const requestCounter = useRef(0);
  const [selectedSymbol, setSelectedSymbol] = useState('all');
  
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
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/loans`, {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'X-API-Key': localStorage.getItem('apiKey')
        }
      });
      
      if (!response.ok) {
        if (response.status === 503 && retryCount < MAX_RETRIES) {
          console.log(`[${currentRequest}] Service unavailable, retrying...`);
          await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
          return fetchLoans(retryCount + 1);
        }
        if (response.status === 403) {
          throw new Error('Unauthorized access');
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

  const availableSymbols = useMemo(() => {
    const symbols = [...new Set(loans.map(loan => loan.symbol))];
    return ['all', ...symbols].sort();
  }, [loans]);

  const filteredBySymbol = useMemo(() => {
    if (selectedSymbol === 'all') {
      return loans;
    }
    return loans.filter(loan => loan.symbol === selectedSymbol);
  }, [loans, selectedSymbol]);

  const filteredLoans = useMemo(() => {
    return rateFilter
      ? filteredBySymbol.filter(loan => loan.rate >= parseFloat(rateFilter))
      : filteredBySymbol;
  }, [filteredBySymbol, rateFilter]);

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
      
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/loans/close`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'X-API-Key': localStorage.getItem('apiKey')
        },
        body: JSON.stringify({
          loan_ids: selectedLoans  // Wrap in object with loan_ids key
        })
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Unauthorized access');
        }
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
      <Grid container spacing={2}>
        <Grid item xs={6}>
          <Typography variant="h4" gutterBottom>
            Active Loans ({filteredLoans.length})
          </Typography>

          <Stack direction="row" spacing={2} mb={2} alignItems="center">
            <FormControl size="small" style={{ minWidth: 120 }}>
              <InputLabel>Symbol</InputLabel>
              <Select
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
                label="Symbol"
              >
                {availableSymbols.map(symbol => (
                  <MenuItem key={symbol} value={symbol}>
                    {symbol === 'all' ? 'All Symbols' : symbol}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
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
        </Grid>

        <Grid item xs={6}>
          {selectedSymbol !== 'all' && (
            <>
              <Typography variant="h6" gutterBottom>
                Funding Book - {selectedSymbol}
              </Typography>
              <FundingBook symbol={selectedSymbol} />
            </>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default LoanTable; 