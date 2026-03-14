/**
 * Dialog shown when approving a rule request would conflict with an existing rule.
 * Displays existing vs proposed rule with differences highlighted; options: update rule or leave as-is.
 */
import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Table,
  TableBody,
  TableRow,
  TableCell,
  TableHead,
} from '@mui/material';
import type { RuleRequest, RuleConflictRule } from '../api/ruleRequests';

function displayUrl(r: RuleConflictRule): string {
  const d = (r.domain_pattern || '').trim();
  const p = (r.path_pattern || '/').trim();
  return (d + (p.startsWith('/') ? p : '/' + p)) || '—';
}

function tagsList(r: RuleConflictRule): string[] {
  const t = r.tags;
  if (Array.isArray(t)) return t;
  return [];
}

function sameTags(a: RuleConflictRule, b: RuleConflictRule): boolean {
  const ta = tagsList(a).slice().sort();
  const tb = tagsList(b).slice().sort();
  return ta.length === tb.length && ta.every((v, i) => v === tb[i]);
}

export interface RuleConflictDialogData {
  request?: RuleRequest | null;
  existing_rule: RuleConflictRule;
  proposed_rule: RuleConflictRule;
}

interface RuleConflictDialogProps {
  open: boolean;
  onClose: () => void;
  data: RuleConflictDialogData | null;
  approving: boolean;
  onUpdate: () => void;
  onLeave: () => void;
}

const DIFF_HIGHLIGHT_EXISTING = { bgcolor: 'warning.light', color: 'warning.contrastText', px: 0.5, borderRadius: 0.5 };
const DIFF_HIGHLIGHT_PROPOSED = { bgcolor: 'success.light', color: 'success.contrastText', px: 0.5, borderRadius: 0.5 };

const RuleConflictDialog: React.FC<RuleConflictDialogProps> = ({
  open,
  onClose,
  data,
  approving,
  onUpdate,
  onLeave,
}) => {
  if (!data) return null;

  const ex = data.existing_rule;
  const prop = data.proposed_rule;

  const urlDiff = displayUrl(ex) !== displayUrl(prop);
  const actionDiff = (ex.action || 'allow') !== (prop.action || 'allow');
  const subdomainsDiff = Boolean(ex.include_subdomains) !== Boolean(prop.include_subdomains);
  const tagsDiff = !sameTags(ex, prop);
  const tfDiff = (ex.text_filter_enabled !== false) !== (prop.text_filter_enabled !== false);
  const imgfDiff = (ex.image_filter_enabled !== false) !== (prop.image_filter_enabled !== false);
  const filefDiff = (ex.file_filter_enabled !== false) !== (prop.file_filter_enabled !== false);

  const actionLabel = (action: string) => (action === 'block' ? 'חסימה' : 'פתיחה');
  const boolLabel = (v: boolean) => (v ? 'כן' : 'לא');
  const filterLabel = (v: boolean) => (v ? 'פעיל' : 'כבוי');

  const CellWithDiff: React.FC<{
    existingVal: React.ReactNode;
    proposedVal: React.ReactNode;
    isDiff: boolean;
    wordBreak?: boolean;
  }> = ({ existingVal, proposedVal, isDiff, wordBreak }) => (
    <>
      <TableCell sx={{ verticalAlign: 'top', py: 0.75, ...(wordBreak && { wordBreak: 'break-all', fontFamily: 'monospace' }) }}>
        {isDiff ? <Box component="span" sx={DIFF_HIGHLIGHT_EXISTING}>{existingVal}</Box> : existingVal}
      </TableCell>
      <TableCell sx={{ verticalAlign: 'top', py: 0.75, ...(wordBreak && { wordBreak: 'break-all', fontFamily: 'monospace' }) }}>
        {isDiff ? <Box component="span" sx={DIFF_HIGHLIGHT_PROPOSED}>{proposedVal}</Box> : proposedVal}
      </TableCell>
    </>
  );

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>הכלל כבר קיים – בחירת פעולה</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          קיים כלל עם אותו דומיין/נתיב אך עם הבדלים. השדות השונים מסומנים. בחר האם לעדכן את הכלל הקיים או להשאירו כמו שהוא.
        </Typography>
        <Table size="small" sx={{ '& td': { borderBottom: '1px solid', borderColor: 'divider' } }}>
          <TableHead>
            <TableRow>
              <TableCell variant="head" sx={{ fontWeight: 600, width: 120 }}>שדה</TableCell>
              <TableCell variant="head" sx={{ fontWeight: 600 }}>הכלל השמור</TableCell>
              <TableCell variant="head" sx={{ fontWeight: 600 }}>מהבקשה (חדש)</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell variant="head" sx={{ fontWeight: 500 }}>כתובת</TableCell>
              <CellWithDiff isDiff={urlDiff} existingVal={displayUrl(ex)} proposedVal={displayUrl(prop)} wordBreak />
            </TableRow>
            <TableRow>
              <TableCell variant="head" sx={{ fontWeight: 500 }}>פעולה</TableCell>
              <CellWithDiff isDiff={actionDiff} existingVal={actionLabel(ex.action || 'allow')} proposedVal={actionLabel(prop.action || 'allow')} />
            </TableRow>
            <TableRow>
              <TableCell variant="head" sx={{ fontWeight: 500 }}>כולל סאב-דומיינים</TableCell>
              <CellWithDiff isDiff={subdomainsDiff} existingVal={boolLabel(!!ex.include_subdomains)} proposedVal={boolLabel(!!prop.include_subdomains)} />
            </TableRow>
            <TableRow>
              <TableCell variant="head" sx={{ fontWeight: 500 }}>תגיות</TableCell>
              <CellWithDiff
                isDiff={tagsDiff}
                existingVal={tagsList(ex).length ? tagsList(ex).join(', ') : '—'}
                proposedVal={tagsList(prop).length ? tagsList(prop).join(', ') : '—'}
              />
            </TableRow>
            {((ex.action || 'allow') === 'allow' || (prop.action || 'allow') === 'allow') && (
              <>
                <TableRow>
                  <TableCell variant="head" sx={{ fontWeight: 500 }}>סינון מלל</TableCell>
                  <CellWithDiff isDiff={tfDiff} existingVal={filterLabel(ex.text_filter_enabled !== false)} proposedVal={filterLabel(prop.text_filter_enabled !== false)} />
                </TableRow>
                <TableRow>
                  <TableCell variant="head" sx={{ fontWeight: 500 }}>סינון תמונות</TableCell>
                  <CellWithDiff isDiff={imgfDiff} existingVal={filterLabel(ex.image_filter_enabled !== false)} proposedVal={filterLabel(prop.image_filter_enabled !== false)} />
                </TableRow>
                <TableRow>
                  <TableCell variant="head" sx={{ fontWeight: 500 }}>סינון קבצים</TableCell>
                  <CellWithDiff isDiff={filefDiff} existingVal={filterLabel(ex.file_filter_enabled !== false)} proposedVal={filterLabel(prop.file_filter_enabled !== false)} />
                </TableRow>
              </>
            )}
          </TableBody>
        </Table>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={approving}>ביטול</Button>
        <Button variant="outlined" onClick={onLeave} disabled={approving}>
          {approving ? '...' : 'השאר כמו שהוא'}
        </Button>
        <Button variant="contained" onClick={onUpdate} disabled={approving}>
          {approving ? 'מאשר...' : 'עדכן את הכלל'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default RuleConflictDialog;
