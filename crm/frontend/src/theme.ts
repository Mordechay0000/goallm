/**
 * MUI Theme configuration - Minimal Admin Design
 * Functional, clean, no marketing elements
 */
import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  direction: 'rtl',
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
      light: '#42a5f5',
      dark: '#1565c0',
      contrastText: '#fff',
    },
    secondary: {
      main: '#424242',
      light: '#6d6d6d',
      dark: '#1d1d1d',
    },
    background: {
      default: '#fafafa',
      paper: '#ffffff',
    },
    text: {
      primary: 'rgba(0, 0, 0, 0.87)',
      secondary: 'rgba(0, 0, 0, 0.6)',
    },
    divider: 'rgba(0, 0, 0, 0.12)',
    action: {
      active: 'rgba(0, 0, 0, 0.54)',
      hover: 'rgba(0, 0, 0, 0.04)',
      selected: 'rgba(25, 118, 210, 0.08)',
      disabled: 'rgba(0, 0, 0, 0.26)',
    },
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontSize: '2rem',
      fontWeight: 600,
      lineHeight: 1.2,
    },
    h2: {
      fontSize: '1.75rem',
      fontWeight: 600,
      lineHeight: 1.3,
    },
    h3: {
      fontSize: '1.5rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h4: {
      fontSize: '1.25rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h5: {
      fontSize: '1.125rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    body1: {
      fontSize: '0.9375rem',
      lineHeight: 1.5,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
    button: {
      textTransform: 'none',
      fontWeight: 500,
      fontSize: '0.9375rem',
    },
  },
  shape: {
    borderRadius: 4,
  },
  shadows: [
    'none',
    '0px 1px 3px rgba(0,0,0,0.12), 0px 1px 2px rgba(0,0,0,0.24)',
    '0px 2px 4px rgba(0,0,0,0.12), 0px 1px 2px rgba(0,0,0,0.24)',
    '0px 3px 6px rgba(0,0,0,0.12), 0px 2px 4px rgba(0,0,0,0.24)',
    '0px 4px 8px rgba(0,0,0,0.12), 0px 2px 4px rgba(0,0,0,0.24)',
    '0px 5px 10px rgba(0,0,0,0.12), 0px 3px 6px rgba(0,0,0,0.24)',
    '0px 6px 12px rgba(0,0,0,0.12), 0px 3px 6px rgba(0,0,0,0.24)',
    '0px 7px 14px rgba(0,0,0,0.12), 0px 4px 8px rgba(0,0,0,0.24)',
    '0px 8px 16px rgba(0,0,0,0.12), 0px 4px 8px rgba(0,0,0,0.24)',
    '0px 9px 18px rgba(0,0,0,0.12), 0px 5px 10px rgba(0,0,0,0.24)',
    '0px 10px 20px rgba(0,0,0,0.12), 0px 5px 10px rgba(0,0,0,0.24)',
    '0px 11px 22px rgba(0,0,0,0.12), 0px 6px 12px rgba(0,0,0,0.24)',
    '0px 12px 24px rgba(0,0,0,0.12), 0px 6px 12px rgba(0,0,0,0.24)',
    '0px 13px 26px rgba(0,0,0,0.12), 0px 7px 14px rgba(0,0,0,0.24)',
    '0px 14px 28px rgba(0,0,0,0.12), 0px 7px 14px rgba(0,0,0,0.24)',
    '0px 15px 30px rgba(0,0,0,0.12), 0px 8px 16px rgba(0,0,0,0.24)',
    '0px 16px 32px rgba(0,0,0,0.12), 0px 8px 16px rgba(0,0,0,0.24)',
    '0px 17px 34px rgba(0,0,0,0.12), 0px 9px 18px rgba(0,0,0,0.24)',
    '0px 18px 36px rgba(0,0,0,0.12), 0px 9px 18px rgba(0,0,0,0.24)',
    '0px 19px 38px rgba(0,0,0,0.12), 0px 10px 20px rgba(0,0,0,00.24)',
    '0px 20px 40px rgba(0,0,0,0.12), 0px 10px 20px rgba(0,0,0,0.24)',
    '0px 21px 42px rgba(0,0,0,0.12), 0px 11px 22px rgba(0,0,0,0.24)',
    '0px 22px 44px rgba(0,0,0,0.12), 0px 11px 22px rgba(0,0,0,0.24)',
    '0px 23px 46px rgba(0,0,0,0.12), 0px 12px 24px rgba(0,0,0,0.24)',
    '0px 24px 48px rgba(0,0,0,0.12), 0px 12px 24px rgba(0,0,0,0.24)',
  ],
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0px 1px 3px rgba(0,0,0,0.12), 0px 1px 2px rgba(0,0,0,0.24)',
          borderRadius: 4,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
        elevation1: {
          boxShadow: '0px 1px 3px rgba(0,0,0,0.12), 0px 1px 2px rgba(0,0,0,0.24)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          borderRadius: 4,
          padding: '8px 16px',
        },
        contained: {
          boxShadow: '0px 1px 3px rgba(0,0,0,0.12), 0px 1px 2px rgba(0,0,0,0.24)',
          '&:hover': {
            boxShadow: '0px 2px 4px rgba(0,0,0,0.12), 0px 1px 2px rgba(0,0,0,0.24)',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 4,
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: '0px 1px 3px rgba(0,0,0,0.12), 0px 1px 2px rgba(0,0,0,0.24)',
        },
      },
    },
  },
});
