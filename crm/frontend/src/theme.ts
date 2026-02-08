/**
 * MUI Theme - שפה עיצובית: Google-Clean + SaaS Enterprise + AI עדין
 * Header: רקע בהיר #eef2f8 כמו שאר האתר, טקסט כהה | Accent: #2F6CFF
 */
import { createTheme } from '@mui/material/styles';

/** גרדיאנט עדין לשימוש רק בקווים דקים, גבולות והדגשות — Blue → Pink → Orange → Yellow → Green */
export const aiSpectrumGradient =
  'linear-gradient(to right, #4A90FF 0%, #FF7ABD 25%, #FFA15E 50%, #F9E67A 75%, #45E68B 100%)';

/** צל עדין מאוד לפי השפה העיצובית */
const cardShadow = '0 4px 18px rgba(0, 0, 0, 0.05)';

export const theme = createTheme({
  direction: 'rtl',
  palette: {
    mode: 'light',
    primary: {
      main: '#0D1A3B',
      light: '#1a2d5c',
      dark: '#080f1f',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#2F6CFF',
      light: '#5a8aff',
      dark: '#2555d9',
      contrastText: '#ffffff',
    },
    background: {
      default: '#F7F8FA',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#1A1A1A',
      secondary: 'rgba(26, 26, 26, 0.55)',
    },
    divider: '#E4E7EC',
    action: {
      active: '#2F6CFF',
      hover: 'rgba(47, 108, 255, 0.06)',
      selected: 'rgba(47, 108, 255, 0.1)',
      disabled: 'rgba(26, 26, 26, 0.35)',
    },
  },
  typography: {
    fontFamily: '"Heebo", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: {
      fontFamily: '"Heebo", sans-serif',
      fontWeight: 600,
      color: '#0D1A3B',
      fontSize: '2rem',
      lineHeight: 1.2,
    },
    h2: {
      fontFamily: '"Heebo", sans-serif',
      fontWeight: 600,
      color: '#0D1A3B',
      fontSize: '1.75rem',
      lineHeight: 1.3,
    },
    h3: {
      fontFamily: '"Heebo", sans-serif',
      fontWeight: 600,
      color: '#0D1A3B',
      fontSize: '1.5rem',
      lineHeight: 1.4,
    },
    h4: {
      fontFamily: '"Heebo", sans-serif',
      fontWeight: 600,
      color: '#0D1A3B',
      fontSize: '1.25rem',
      lineHeight: 1.4,
    },
    h5: {
      fontFamily: '"Heebo", sans-serif',
      fontWeight: 600,
      color: '#0D1A3B',
      fontSize: '1.125rem',
      lineHeight: 1.5,
    },
    h6: {
      fontFamily: '"Heebo", sans-serif',
      fontWeight: 600,
      color: '#0D1A3B',
      fontSize: '1rem',
      lineHeight: 1.5,
    },
    body1: {
      fontFamily: '"Heebo", sans-serif',
      fontWeight: 400,
      fontSize: '1rem',
      lineHeight: 1.6,
      color: '#1A1A1A',
    },
    body2: {
      fontFamily: '"Heebo", sans-serif',
      fontWeight: 400,
      fontSize: '0.9375rem',
      lineHeight: 1.6,
      color: '#1A1A1A',
    },
    button: {
      fontFamily: '"Heebo", sans-serif',
      textTransform: 'none',
      fontWeight: 500,
      fontSize: '1rem',
    },
    caption: {
      fontFamily: '"Assistant", "Heebo", sans-serif',
      fontSize: '0.875rem',
    },
  },
  shape: {
    borderRadius: 24,
  },
  shadows: [
    'none',
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
    cardShadow,
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          fontFamily: '"Heebo", sans-serif',
          color: '#1A1A1A',
        },
        /* גלילה ברירת מחדל – אפור (סיידבר, דפים כלליים) */
        '*': {
          scrollbarWidth: 'thin',
          scrollbarColor: '#A8B4C8 #E4E7EC',
        },
        '*::-webkit-scrollbar': {
          width: 10,
          height: 10,
        },
        '*::-webkit-scrollbar-track': {
          background: '#E4E7EC',
          borderRadius: 10,
        },
        '*::-webkit-scrollbar-thumb': {
          background: '#A8B4C8',
          borderRadius: 10,
          border: '2px solid #E4E7EC',
          minHeight: 40,
          minWidth: 40,
        },
        '*::-webkit-scrollbar-thumb:hover': {
          background: '#8A96A8',
        },
        '*::-webkit-scrollbar-corner': {
          background: '#E4E7EC',
          borderRadius: 10,
        },
      },
    },
    /* טבלאות ואזורי תוכן – גלילה בכחול הראשי */
    MuiTableContainer: {
      styleOverrides: {
        root: {
          scrollbarColor: '#2F6CFF #E4E7EC',
          '&::-webkit-scrollbar': { width: 10, height: 10 },
          '&::-webkit-scrollbar-track': { background: '#E4E7EC', borderRadius: 10 },
          '&::-webkit-scrollbar-thumb': {
            background: '#2F6CFF',
            borderRadius: 10,
            border: '2px solid #E4E7EC',
            minHeight: 40,
            minWidth: 40,
          },
          '&::-webkit-scrollbar-thumb:hover': { background: '#2555d9' },
          '&::-webkit-scrollbar-corner': { background: '#E4E7EC', borderRadius: 10 },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: cardShadow,
          borderRadius: 24,
          border: '1px solid #E4E7EC',
          overflow: 'hidden',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          borderRadius: 24,
          border: '1px solid #E4E7EC',
          boxShadow: cardShadow,
        },
        elevation1: {
          boxShadow: cardShadow,
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          borderRadius: 24,
          padding: '10px 20px',
          transition: 'background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease',
        },
        contained: {
          backgroundColor: '#2F6CFF',
          color: '#ffffff',
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.06)',
          '&:hover': {
            backgroundColor: '#2555d9',
            boxShadow: '0 4px 14px rgba(47, 108, 255, 0.22)',
          },
        },
        outlined: {
          borderColor: '#E4E7EC',
          color: '#0D1A3B',
          '&:hover': {
            borderColor: '#2F6CFF',
            backgroundColor: 'rgba(47, 108, 255, 0.06)',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 20,
            backgroundColor: '#FFFFFF',
            '& fieldset': {
              borderColor: '#E4E7EC',
            },
            '&:hover fieldset': {
              borderColor: '#2F6CFF',
            },
            '&.Mui-focused fieldset': {
              borderWidth: '2px',
              borderColor: '#2F6CFF',
            },
          },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 20,
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: '#2F6CFF',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#eef2f8',
          color: '#0D1A3B',
          boxShadow: cardShadow,
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          color: '#2F6CFF',
          borderRadius: 20,
          '&:hover': {
            backgroundColor: 'rgba(47, 108, 255, 0.08)',
          },
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 20,
          '&:hover': {
            backgroundColor: 'rgba(47, 108, 255, 0.06)',
          },
          '&.Mui-selected': {
            backgroundColor: 'rgba(47, 108, 255, 0.1)',
            '& .MuiListItemIcon-root': {
              color: '#2F6CFF',
            },
            '&:hover': {
              backgroundColor: 'rgba(47, 108, 255, 0.12)',
            },
          },
        },
      },
    },
    MuiListItemIcon: {
      styleOverrides: {
        root: {
          color: '#2F6CFF',
          minWidth: 44,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: '#F4F7FF',
          },
          'thead &': {
            '&:hover': {
              backgroundColor: 'transparent',
            },
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          fontFamily: '"Assistant", "Heebo", sans-serif',
          borderBottom: '1px solid #E4E7EC',
        },
        head: {
          fontFamily: '"Heebo", sans-serif',
          fontWeight: 600,
          color: '#080f1f',
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          '&:hover': {
            backgroundColor: 'rgba(47, 108, 255, 0.08)',
          },
        },
      },
    },
    MuiCardActionArea: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(47, 108, 255, 0.06)',
          },
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: '#E4E7EC',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 16,
          fontFamily: '"Heebo", sans-serif',
        },
      },
    },
    MuiBadge: {
      styleOverrides: {
        colorPrimary: {
          backgroundColor: '#2F6CFF',
        },
      },
    },
    MuiLink: {
      styleOverrides: {
        root: {
          color: '#2F6CFF',
          '&:hover': {
            color: '#2555d9',
          },
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 24,
          boxShadow: cardShadow,
          border: '1px solid #E4E7EC',
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 20,
          fontFamily: '"Heebo", sans-serif',
        },
      },
    },
  },
});
