/**
 * Loaded in iframe from CRM origin. Reports auth state (logged_in, is_admin) to parent.
 * When admin, listens for do-block / do-update-rule from parent and performs them (using token).
 */
import React, { useEffect, useRef } from 'react';
import apiClient from '../api/client';
import { adminApi } from '../api/admin';

const AUTH_MESSAGE_TYPE = 'goallm-surf-auth';

function sendAuth(loggedIn: boolean, isAdmin: boolean) {
  try {
    window.parent.postMessage(
      { type: AUTH_MESSAGE_TYPE, logged_in: loggedIn, is_admin: isAdmin },
      '*'
    );
  } catch {
    // ignore
  }
}

export const SurfAdminCheckPage: React.FC = () => {
  const sentRef = useRef(false);

  useEffect(() => {
    if (sentRef.current) return;
    const token = localStorage.getItem('access_token');
    if (!token) {
      sendAuth(false, false);
      sentRef.current = true;
      return;
    }
    apiClient
      .get<{ is_admin?: boolean }>('/api/me')
      .then((res) => {
        const isAdmin = res.data?.is_admin === true;
        sendAuth(true, isAdmin);
        sentRef.current = true;
      })
      .catch(() => {
        sendAuth(false, false);
        sentRef.current = true;
      });
  }, []);

  useEffect(() => {
    const handle = (e: MessageEvent) => {
      const d = e.data;
      if (!d || typeof d !== 'object' || !d.type) return;
      if (d.type === 'goallm-surf-do-block' && typeof d.url === 'string') {
        const url = d.url.trim();
        if (!url) {
          window.parent.postMessage({ type: 'goallm-surf-block-done', success: false, error: 'חסר כתובת' }, '*');
          return;
        }
        const fullUrl = url.includes('://') ? url : `https://${url}`;
        adminApi
          .createGlobalRule({ url: fullUrl, action: 'block', include_subdomains: true })
          .then(() => {
            window.parent.postMessage({ type: 'goallm-surf-block-done', success: true }, '*');
          })
          .catch((err: { response?: { data?: { detail?: string } }; message?: string }) => {
            window.parent.postMessage({
              type: 'goallm-surf-block-done',
              success: false,
              error: err?.response?.data?.detail || err?.message || 'שגיאה',
            }, '*');
          });
      }
      if (d.type === 'goallm-surf-do-update-rule' && typeof d.rule_domain === 'string') {
        const ruleDomain = d.rule_domain.trim();
        const rulePath = (d.rule_path != null && d.rule_path !== undefined) ? String(d.rule_path).trim() || '/' : '/';
        adminApi
          .surfUpdateRuleToBlock(ruleDomain, rulePath)
          .then(() => {
            window.parent.postMessage({ type: 'goallm-surf-update-done', success: true }, '*');
          })
          .catch((err: { response?: { data?: { detail?: string } }; message?: string }) => {
            window.parent.postMessage({
              type: 'goallm-surf-update-done',
              success: false,
              error: err?.response?.data?.detail || err?.message || 'שגיאה',
            }, '*');
          });
      }
    };
    window.addEventListener('message', handle);
    return () => window.removeEventListener('message', handle);
  }, []);

  return null;
};

export default SurfAdminCheckPage;
