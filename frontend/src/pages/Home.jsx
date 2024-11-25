import React from 'react';
import { Container, Box } from '@mui/material';
import LoanTable from '../components/LoanTable';

const Home = () => {
  return (
    <Container maxWidth="xl">
      <Box py={4}>
        <LoanTable />
      </Box>
    </Container>
  );
};

export default Home; 