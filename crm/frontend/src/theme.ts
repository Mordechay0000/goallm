/**
 * שפת עיצוב ממותגת — Deep Blue + AI Violet
 * אמינות, חדשנות, פרימיום. Apple clarity + Google accessibility.
 * כל הרכיבים חלים על כל הדפים, תיבות דו־שיח והמערכת.
 */
import { createTheme } from '@mui/material/styles';

/* —— צבעי מותג (פסיכולוגיה) —— */
const deepBlue = '#1e3a5f';           /* אמינות, רצינות, ביטחון */
const deepBlueLight = '#2d4a6f';
const deepBlueDark = '#152a45';
const aiViolet = '#5b21b6';           /* חדשנות, פרימיום — שימוש מאוזן */
const aiVioletLight = '#6d28d9';
const aiVioletDark = '#4c1d95';
const electricBlue = '#2563eb';      /* הדגשה מינימלית — כפתורים ראשיים */
const electricBlueHover = '#1d4ed8';
const white = '#ffffff';
const lightGray = '#f8fafc';
const grayBorder = '#e2e8f0';
const textPrimary = '#0f172a';
const textBody = '#334155';
const textSecondary = '#64748b';
const iconDefault = '#334155';       /* אייקונים: אפור כהה / כחול כהה */

/* —— צללים (Apple עדין + Google מפוזר) —— */
const shadowCard = '0 1px 3px rgba(0, 0, 0, 0.04)';
const shadowCardHover = '0 4px 12px rgba(0, 0, 0, 0.08)';
const shadowDialog = '0 20px 40px rgba(0, 0, 0, 0.1), 0 8px 16px rgba(0, 0, 0, 0.06)';

/* —— גרדיאנט עדין (3–5% opacity) — כותרות מרכזיות בלבד —— */
export const brandGradientSubtle = 'linear-gradient(135deg, rgba(30, 58, 95, 0.04) 0%, rgba(91, 33, 182, 0.04) 100%)';

export const theme = createTheme({
  direction: 'rtl',
  palette: {
    mode: 'light',
    primary: {
      main: deepBlue,
      light: deepBlueLight,
      dark: deepBlueDark,
      contrastText: white,
    },
    secondary: {
      main: aiViolet,
      light: aiVioletLight,
      dark: aiVioletDark,
      contrastText: white,
    },
    success: {
      main: '#0d9488',
      light: '#14b8a6',
      dark: '#0f766e',
      contrastText: white,
    },
    error: {
      main: '#dc2626',
      light: '#ef4444',
      dark: '#b91c1c',
      contrastText: white,
    },
    background: {
      default: lightGray,
      paper: white,
    },
    text: {
      primary: textPrimary,
      secondary: textSecondary,
    },
    divider: grayBorder,
    action: {
      active: electricBlue,
      hover: 'rgba(30, 58, 95, 0.06)',
      selected: 'rgba(30, 58, 95, 0.08)',
      disabled: 'rgba(15, 23, 42, 0.38)',
    },
  },
  typography: {
    fontFamily: '"Rubik", "Assistant", -apple-system, BlinkMacSystemFont, sans-serif',
    h1: {
      fontFamily: '"Assistant", "Rubik", sans-serif',
      fontWeight: 600,
      color: textPrimary,
      fontSize: '2rem',
      lineHeight: 1.25,
    },
    h2: {
      fontFamily: '"Assistant", "Rubik", sans-serif',
      fontWeight: 500,
      color: textPrimary,
      fontSize: '1.75rem',
      lineHeight: 1.3,
    },
    h3: {
      fontFamily: '"Assistant", "Rubik", sans-serif',
      fontWeight: 600,
      color: textPrimary,
      fontSize: '1.5rem',
      lineHeight: 1.35,
    },
    h4: {
      fontFamily: '"Assistant", "Rubik", sans-serif',
      fontWeight: 600,
      color: textPrimary,
      fontSize: '1.25rem',
      lineHeight: 1.4,
    },
    h5: {
      fontFamily: '"Assistant", "Rubik", sans-serif',
      fontWeight: 600,
      color: textPrimary,
      fontSize: '1.125rem',
      lineHeight: 1.45,
    },
    h6: {
      fontFamily: '"Assistant", "Rubik", sans-serif',
      fontWeight: 600,
      color: textPrimary,
      fontSize: '1rem',
      lineHeight: 1.5,
    },
    body1: {
      fontFamily: '"Rubik", sans-serif',
      fontWeight: 400,
      fontSize: '1rem',
      lineHeight: 1.6,
      color: textBody,
    },
    body2: {
      fontFamily: '"Rubik", sans-serif',
      fontWeight: 400,
      fontSize: '0.9375rem',
      lineHeight: 1.6,
      color: textBody,
    },
    button: {
      fontFamily: '"Rubik", sans-serif',
      textTransform: 'none',
      fontWeight: 500,
      fontSize: '1rem',
    },
    caption: {
      fontFamily: '"Rubik", sans-serif',
      fontSize: '0.875rem',
      fontWeight: 500,
      color: textSecondary,
    },
    subtitle1: {
      fontFamily: '"Rubik", sans-serif',
      fontWeight: 500,
      fontSize: '0.9375rem',
      color: textSecondary,
    },
    subtitle2: {
      fontFamily: '"Rubik", sans-serif',
      fontWeight: 500,
      fontSize: '0.8125rem',
      color: textSecondary,
    },
  },
  shape: {
    borderRadius: 12,
  },
  shadows: [
    'none',
    shadowCard,
    shadowCard,
    shadowCard,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
    shadowCardHover,
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          fontFamily: '"Rubik", sans-serif',
          color: textBody,
        },
        '*': {
          scrollbarWidth: 'thin',
          scrollbarColor: '#94a3b8 ' + grayBorder,
        },
        '*::-webkit-scrollbar': { width: 8, height: 8 },
        '*::-webkit-scrollbar-track': { background: grayBorder, borderRadius: 8 },
        '*::-webkit-scrollbar-thumb': {
          background: '#94a3b8',
          borderRadius: 8,
          border: '2px solid ' + grayBorder,
          minHeight: 32,
          minWidth: 32,
        },
        '*::-webkit-scrollbar-thumb:hover': { background: '#64748b' },
        '*::-webkit-scrollbar-corner': { background: grayBorder, borderRadius: 8 },
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          scrollbarColor: deepBlue + ' ' + grayBorder,
          '&::-webkit-scrollbar-thumb': { background: deepBlue },
          '&::-webkit-scrollbar-thumb:hover': { background: deepBlueDark },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 16,
          border: '1px solid ' + grayBorder,
          boxShadow: shadowCard,
          overflow: 'hidden',
          transition: 'box-shadow 0.2s ease',
          '&:hover': {
            boxShadow: shadowCardHover,
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          borderRadius: 16,
          border: '1px solid ' + grayBorder,
          boxShadow: shadowCard,
          transition: 'box-shadow 0.2s ease',
          '&:hover': {
            boxShadow: shadowCardHover,
          },
        },
        elevation1: { boxShadow: shadowCard },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          padding: '10px 20px',
          transition: 'background-color 0.2s ease, box-shadow 0.2s ease',
        },
        contained: {
          backgroundColor: electricBlue,
          color: white,
          boxShadow: shadowCard,
          '&:hover': {
            backgroundColor: electricBlueHover,
            boxShadow: shadowCardHover,
          },
        },
        outlined: {
          borderColor: grayBorder,
          color: deepBlue,
          backgroundColor: 'transparent',
          '&:hover': {
            borderColor: deepBlue,
            backgroundColor: 'rgba(30, 58, 95, 0.06)',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 12,
            backgroundColor: white,
            '& fieldset': { borderColor: grayBorder },
            '&:hover fieldset': { borderColor: deepBlue },
            '&.Mui-focused fieldset': {
              borderWidth: '2px',
              borderColor: deepBlue,
            },
          },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: deepBlue },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: white,
          color: deepBlue,
          boxShadow: shadowCard,
          borderBottom: '1px solid ' + grayBorder,
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          color: iconDefault,
          borderRadius: 12,
          transition: 'background-color 0.2s ease',
          '&:hover': {
            backgroundColor: 'rgba(30, 58, 95, 0.06)',
            color: deepBlue,
          },
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          transition: 'background-color 0.2s ease',
          '&:hover': {
            backgroundColor: 'rgba(30, 58, 95, 0.06)',
          },
          '&.Mui-selected': {
            backgroundColor: 'rgba(30, 58, 95, 0.08)',
            '& .MuiListItemIcon-root': { color: electricBlue },
            '&:hover': { backgroundColor: 'rgba(30, 58, 95, 0.1)' },
          },
        },
      },
    },
    MuiListItemIcon: {
      styleOverrides: {
        root: {
          color: iconDefault,
          minWidth: 40,
          '& .MuiSvgIcon-root': { fontSize: '1.25rem' },
          '.Mui-selected &': { color: electricBlue },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 0.15s ease',
          '&:hover': { backgroundColor: 'rgba(30, 58, 95, 0.04)' },
          '&.Mui-selected': {
            backgroundColor: 'rgba(30, 58, 95, 0.06)',
            '&:hover': { backgroundColor: 'rgba(30, 58, 95, 0.08)' },
          },
          'thead &': { '&:hover': { backgroundColor: 'transparent' } },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          fontFamily: '"Rubik", sans-serif',
          borderBottom: '1px solid ' + grayBorder,
          paddingLeft: 16,
          paddingRight: 16,
        },
        head: {
          fontFamily: '"Assistant", "Rubik", sans-serif',
          fontWeight: 600,
          color: textPrimary,
          backgroundColor: lightGray,
          borderBottom: '2px solid ' + grayBorder,
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          '&:hover': { backgroundColor: 'rgba(30, 58, 95, 0.06)' },
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: { borderColor: grayBorder },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          fontFamily: '"Rubik", sans-serif',
        },
      },
    },
    MuiBadge: {
      styleOverrides: {
        colorPrimary: { backgroundColor: electricBlue },
      },
    },
    MuiLink: {
      styleOverrides: {
        root: {
          color: electricBlue,
          '&:hover': { color: electricBlueHover },
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 16,
          boxShadow: shadowDialog,
          border: '1px solid ' + grayBorder,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          fontFamily: '"Rubik", sans-serif',
          '&.MuiAlert-standardSuccess': {
            backgroundColor: 'rgba(13, 148, 136, 0.1)',
            color: '#0f766e',
            '& .MuiAlert-icon': { color: '#0d9488' },
          },
          '&.MuiAlert-standardError': {
            backgroundColor: 'rgba(220, 38, 38, 0.1)',
            color: '#b91c1c',
            '& .MuiAlert-icon': { color: '#dc2626' },
          },
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          height: 3,
          borderRadius: 2,
          backgroundColor: grayBorder,
        },
        bar: {
          borderRadius: 2,
          background: `linear-gradient(90deg, ${deepBlue} 0%, ${aiViolet} 100%)`,
        },
      },
    },
  },
});
