/**
 * useOrgTypes — dynamic "Acting As / Organization type" master.
 * Fetches the admin-managed list from GET /api/org-types (single source of
 * truth, CRUD under Admin → Masters → Org Types). Falls back to the bundled
 * defaults if the API is unreachable so intake screens never render empty.
 */
import { useEffect, useState } from 'react';
import api from '../utils/api';

export interface OrgType {
  key: string;
  label: string;
  icon: string;
  color: string;
  desc: string;
  is_org: boolean;
}

export const DEFAULT_ORG_TYPES: OrgType[] = [
  { key: 'INDIVIDUAL',    label: 'Individual',              icon: 'person',        color: '#6366F1', desc: 'Self / personal',             is_org: false },
  { key: 'FAMILY',        label: 'Family',                  icon: 'people',        color: '#EC4899', desc: 'Family / household',          is_org: false },
  { key: 'BUSINESS_ORG',  label: 'Business Organization',   icon: 'business',      color: '#0EA5E9', desc: 'Company / startup / SMB',     is_org: true },
  { key: 'ACADEMIC_ORG',  label: 'Academic Organization',   icon: 'school',        color: '#F59E0B', desc: 'School / college / research', is_org: true },
  { key: 'NONPROFIT_ORG', label: 'Non-profit Organization', icon: 'heart',         color: '#10B981', desc: 'NGO / charity / foundation',  is_org: true },
  { key: 'ASSOCIATION',   label: 'Association',             icon: 'people-circle', color: '#F43F5E', desc: 'Society / club / housing',    is_org: true },
  { key: 'GOVERNMENT',    label: 'Government',              icon: 'globe',         color: '#8B5CF6', desc: 'Public / policy / civic',     is_org: true },
];

export function useOrgTypes() {
  const [orgTypes, setOrgTypes] = useState<OrgType[]>(DEFAULT_ORG_TYPES);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api.get('/org-types')
      .then(r => {
        if (!alive) return;
        const items: OrgType[] = (r.data || []).map((o: any) => ({
          key: o.key,
          label: o.label || o.key,
          icon: o.icon || 'ellipse',
          color: o.color || '#6366F1',
          desc: o.description || '',
          is_org: !!o.is_org,
        }));
        if (items.length) setOrgTypes(items);
      })
      .catch(() => { /* keep bundled defaults */ })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  return { orgTypes, loading };
}
