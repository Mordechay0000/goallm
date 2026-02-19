/**
 * לוגו מותג — עגול-מופשט, כחול-סגול, AI + דיוק.
 * אייקון מותג נקי מאוד.
 */
import React from 'react';
import { Box, Typography } from '@mui/material';
import { BRAND } from '../brand';

const LOGO_MARK_SIZE = 36;

/** סימן לוגו — גרדיאנט כחול → סגול, עגול, מינימלי */
export const BrandLogoMark: React.FC<{ size?: number; className?: string }> = ({
  size = LOGO_MARK_SIZE,
  className,
}) => (
  <Box
    className={className}
    sx={{
      width: size,
      height: size,
      borderRadius: '50%',
      background: 'linear-gradient(135deg, #1e3a5f 0%, #5b21b6 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
    }}
    aria-hidden
  >
    <svg
      width={size * 0.5}
      height={size * 0.5}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      stroke="rgba(255,255,255,0.95)"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  </Box>
);

/** לוגו מלא — סימן + שם */
const BrandLogo: React.FC<{
  showName?: boolean;
  size?: 'sidebar' | 'small';
  className?: string;
}> = ({ showName = true, size = 'sidebar', className }) => {
  const markSize = size === 'sidebar' ? 40 : 32;
  return (
    <Box
      className={className}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.25,
      }}
    >
      <BrandLogoMark size={markSize} />
      {showName && (
        <Typography
          variant="h6"
          component="span"
          sx={{
            fontFamily: '"Assistant", "Rubik", sans-serif',
            fontWeight: 600,
            fontSize: size === 'sidebar' ? '1.2rem' : '1rem',
            color: '#0f172a',
            letterSpacing: '-0.02em',
            lineHeight: 1.2,
          }}
        >
          {BRAND.appName}
        </Typography>
      )}
    </Box>
  );
};

export default BrandLogo;
