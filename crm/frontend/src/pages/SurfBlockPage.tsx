/**
 * Admin-only page: open from surf widget to create a block rule for the given URL.
 * Query: url=... (full URL or domain). Acts only after an explicit click – opening a crafted link
 * must not change rules by itself.
 */
import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Typography, CircularProgress, Button } from '@mui/material';
import { adminApi } from '../api/admin';

const SurfBlockPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const url = searchParams.get('url')?.trim() || '';

  const apply = async () => {
    if (!url) {
      setStatus('error');
      setMessage('חסר פרמטר url');
      return;
    }
    setStatus('loading');
    const fullUrl = url.includes('://') ? url : `https://${url}`;
    try {
      await adminApi.createGlobalRule({ url: fullUrl, action: 'block', include_subdomains: true });
      setStatus('ok');
      setMessage('האתר נחסם בהצלחה.');
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string };
      setStatus('error');
      setMessage(ax?.response?.data?.detail || ax?.message || 'שגיאה בחסימת האתר');
    }
  };

  return (
    <Box sx={{ p: 3, textAlign: 'center' }}>
      {status === 'idle' && (
        <>
          <Typography sx={{ mb: 2, wordBreak: 'break-all' }}>לחסום ברשימה הגלובלית: {url || '—'}</Typography>
          <Button variant="contained" color="error" onClick={apply}>
            אשר חסימה
          </Button>
        </>
      )}
      {status === 'loading' && <CircularProgress />}
      {status === 'ok' && <Typography color="success.main">{message}</Typography>}
      {status === 'error' && <Typography color="error">{message}</Typography>}
    </Box>
  );
};

export default SurfBlockPage;
