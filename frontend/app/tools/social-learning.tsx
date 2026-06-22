import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  Platform,
  KeyboardAvoidingView,
  Modal,
  FlatList,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as DocumentPicker from 'expo-document-picker';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

// ========================
// CONSTANTS
// ========================

const TABS = [
  { key: 'upload', label: 'Upload', icon: 'cloud-upload' },
  { key: 'my', label: 'My Templates', icon: 'document-text' },
  { key: 'browse', label: 'Browse', icon: 'globe' },
  { key: 'premium', label: 'Premium', icon: 'diamond' },
];

const INPUT_MODES = [
  { key: 'text', label: 'Text', icon: 'create', desc: 'Paste news article' },
  { key: 'url', label: 'URL', icon: 'link', desc: 'Fetch from link' },
  { key: 'file', label: 'File', icon: 'document-attach', desc: 'PDF, DOCX, TXT, Image' },
  { key: 'audio', label: 'Audio/Video', icon: 'mic', desc: 'English only' },
];

const CATEGORY_ICONS: Record<string, { icon: string; color: string }> = {
  problem: { icon: 'warning', color: '#EF4444' },
  need: { icon: 'bulb', color: '#F59E0B' },
  aspiration: { icon: 'rocket', color: '#10B981' },
};

const TIER_LABELS: Record<number, { label: string; color: string; bg: string }> = {
  1: { label: 'Personal', color: '#6B7280', bg: '#F3F4F6' },
  2: { label: 'Authorized', color: '#059669', bg: '#ECFDF5' },
  3: { label: 'Premium', color: '#7C3AED', bg: '#F5F3FF' },
};

const STATUS_COLORS: Record<string, { color: string; bg: string }> = {
  draft: { color: '#6B7280', bg: '#F3F4F6' },
  submitted: { color: '#3B82F6', bg: '#EFF6FF' },
  authorized: { color: '#059669', bg: '#ECFDF5' },
  rejected: { color: '#EF4444', bg: '#FEF2F2' },
};

const LIFE_AREA_LABELS: Record<string, string> = {
  career_profession: 'Career & Profession',
  finance_wealth: 'Finance & Wealth',
  health_wellness: 'Health & Wellness',
  relationships_family: 'Relationships & Family',
  education_learning: 'Education & Learning',
  personal_growth: 'Personal Growth',
  social_community: 'Social & Community',
  legal_governance: 'Legal & Governance',
  technology_innovation: 'Technology & Innovation',
  environment_sustainability: 'Environment & Sustainability',
};

const LANGUAGES = [
  { code: 'english', label: 'English' },
  { code: 'hindi', label: 'Hindi' },
  { code: 'tamil', label: 'Tamil' },
  { code: 'telugu', label: 'Telugu' },
  { code: 'kannada', label: 'Kannada' },
  { code: 'malayalam', label: 'Malayalam' },
];

// ========================
// MAIN COMPONENT
// ========================

export default function SocialLearningScreen() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('upload');
  const [refreshing, setRefreshing] = useState(false);

  // Upload State
  const [inputMode, setInputMode] = useState('text');
  const [newsText, setNewsText] = useState('');
  const [newsUrl, setNewsUrl] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [title, setTitle] = useState('');
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<any>(null);
  const [lastResult, setLastResult] = useState<any>(null);

  // My Templates
  const [myTemplates, setMyTemplates] = useState<any[]>([]);
  const [myLoading, setMyLoading] = useState(false);
  const [myFilter, setMyFilter] = useState('all');

  // Browse (Authorized Tier 2)
  const [authorizedTemplates, setAuthorizedTemplates] = useState<any[]>([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [browseFilter, setBrowseFilter] = useState('');
  const [browseSearch, setBrowseSearch] = useState('');

  // Premium (Tier 3)
  const [premiumSolutions, setPremiumSolutions] = useState<any[]>([]);
  const [premiumLoading, setPremiumLoading] = useState(false);

  // Stats
  const [stats, setStats] = useState<any>(null);

  // Detail Modal
  const [detailModal, setDetailModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // ========================
  // DATA FETCHING
  // ========================

  const fetchMyTemplates = async () => {
    setMyLoading(true);
    try {
      const params: any = { limit: 50 };
      if (myFilter !== 'all') params.status = myFilter;
      const res = await api.get('/social-learning/my-templates', { params });
      setMyTemplates(res.data?.templates || []);
    } catch (e) {
      console.error('Failed to load templates:', e);
    } finally {
      setMyLoading(false);
    }
  };

  const fetchAuthorized = async () => {
    setBrowseLoading(true);
    try {
      const params: any = { limit: 50 };
      if (browseFilter) params.life_area = browseFilter;
      if (browseSearch) params.search = browseSearch;
      const res = await api.get('/social-learning/authorized', { params });
      setAuthorizedTemplates(res.data?.templates || []);
    } catch (e) {
      console.error('Failed to load authorized:', e);
    } finally {
      setBrowseLoading(false);
    }
  };

  const fetchPremium = async () => {
    setPremiumLoading(true);
    try {
      const res = await api.get('/social-learning/solutions', { params: { limit: 50 } });
      setPremiumSolutions(res.data?.solutions || []);
    } catch (e) {
      console.error('Failed to load premium:', e);
    } finally {
      setPremiumLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await api.get('/social-learning/stats');
      setStats(res.data);
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchStats();
      if (activeTab === 'my') fetchMyTemplates();
      if (activeTab === 'browse') fetchAuthorized();
      if (activeTab === 'premium') fetchPremium();
    }, [activeTab, myFilter, browseFilter])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchStats();
    if (activeTab === 'my') await fetchMyTemplates();
    if (activeTab === 'browse') await fetchAuthorized();
    if (activeTab === 'premium') await fetchPremium();
    setRefreshing(false);
  };

  // ========================
  // UPLOAD HANDLERS
  // ========================

  const handleTextUpload = async () => {
    if (!newsText || newsText.trim().length < 50) {
      showAlert('Minimum Length', 'Please enter at least 50 characters of news content.');
      return;
    }
    setUploading(true);
    try {
      const res = await api.post('/social-learning/upload', {
        content: newsText,
        source_url: sourceUrl || undefined,
        source_name: sourceName || undefined,
        title: title || undefined,
      });
      setLastResult(res.data);
      setNewsText('');
      setSourceUrl('');
      setSourceName('');
      setTitle('');
      showAlert('Success', 'News classified and template created!');
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to upload news');
    } finally {
      setUploading(false);
    }
  };

  const handleUrlUpload = async () => {
    const trimmedUrl = newsUrl.trim();
    if (!trimmedUrl || !trimmedUrl.startsWith('http')) {
      showAlert('Invalid URL', 'Please enter a valid URL starting with http:// or https://');
      return;
    }
    setUploading(true);
    try {
      const res = await api.post('/social-learning/upload-url', {
        url: trimmedUrl,
        title: title || undefined,
        source_name: sourceName || undefined,
      }, { timeout: 60000 });
      setLastResult(res.data);
      setNewsUrl('');
      setTitle('');
      setSourceName('');
      showAlert('Success', 'URL content fetched, classified, and template created!');
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to fetch URL');
    } finally {
      setUploading(false);
    }
  };

  const handleFilePick = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          'application/pdf',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'text/plain',
          'image/jpeg',
          'image/png',
          'image/webp',
        ],
        copyToCacheDirectory: true,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        setSelectedFile(result.assets[0]);
      }
    } catch (e) {
      showAlert('Error', 'Failed to pick file');
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) {
      showAlert('No File', 'Please select a file first');
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', {
        uri: selectedFile.uri,
        name: selectedFile.name || 'upload',
        type: selectedFile.mimeType || 'application/octet-stream',
      } as any);
      if (title) formData.append('title', title);
      if (sourceName) formData.append('source_name', sourceName);
      if (sourceUrl) formData.append('source_url', sourceUrl);

      const res = await api.post('/social-learning/upload-file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      setLastResult(res.data);
      setSelectedFile(null);
      setTitle('');
      setSourceName('');
      setSourceUrl('');
      showAlert('Success', 'File processed and template created!');
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to process file');
    } finally {
      setUploading(false);
    }
  };

  const handleAudioUpload = async () => {
    // Pick audio or video file via document picker
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['audio/*', 'video/*'],
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets || result.assets.length === 0) return;

      const mediaFile = result.assets[0];
      setUploading(true);

      const formData = new FormData();
      formData.append('audio', {
        uri: mediaFile.uri,
        name: mediaFile.name || 'media.wav',
        type: mediaFile.mimeType || 'audio/wav',
      } as any);
      if (title) formData.append('title', title);
      if (sourceName) formData.append('source_name', sourceName);

      const res = await api.post('/social-learning/upload-audio', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      setLastResult(res.data);
      setTitle('');
      setSourceName('');
      showAlert('Success', 'Media transcribed and template created!');
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to process media');
    } finally {
      setUploading(false);
    }
  };

  // ========================
  // TEMPLATE ACTIONS
  // ========================

  const handleSubmit = async (templateId: string) => {
    try {
      await api.post(`/social-learning/template/${templateId}/submit`);
      showAlert('Submitted', 'Template submitted for admin review!');
      fetchMyTemplates();
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to submit');
    }
  };

  const handleDelete = async (templateId: string) => {
    showAlert('Delete', 'Are you sure you want to delete this template?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/social-learning/template/${templateId}`);
            showAlert('Deleted', 'Template removed');
            fetchMyTemplates();
          } catch (e: any) {
            showAlert('Error', e.response?.data?.detail || 'Failed to delete');
          }
        },
      },
    ]);
  };

  const openDetail = async (templateId: string, isSolution: boolean = false) => {
    setDetailLoading(true);
    setDetailModal(true);
    try {
      const endpoint = isSolution
        ? `/social-learning/solution/${templateId}`
        : `/social-learning/template/${templateId}`;
      const res = await api.get(endpoint);
      setSelectedTemplate({ ...res.data, _isSolution: isSolution });
    } catch (e) {
      showAlert('Error', 'Failed to load template details');
      setDetailModal(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleUseInDecision = (template: any) => {
    // Navigate to new decision with pre-filled data from template
    const scenario = template.life_scenario_template || template.premium_life_scenario || {};
    const decisionEP = scenario.decision_entry_point || {};
    router.push({
      pathname: '/tools/new-decision',
      params: {
        prefill_title: decisionEP.problem_statement || template.title || '',
        prefill_context: template.english_summary || '',
        prefill_factors: JSON.stringify(decisionEP.key_factors || []),
        prefill_options: JSON.stringify(decisionEP.options_to_evaluate || []),
        from_social_learning: template.id,
      },
    });
    setDetailModal(false);
  };

  const handleUseInSolutionFinder = (template: any) => {
    const scenario = template.life_scenario_template || template.premium_life_scenario || {};
    const sfEP = scenario.solution_finder_entry_point || {};
    router.push({
      pathname: '/tools/solution-finder',
      params: {
        prefill_goal: sfEP.smart_goal || '',
        prefill_concerns: (sfEP.main_concerns || []).join('\n'),
        prefill_risks: (sfEP.risk_management_questions || []).join('\n'),
        prefill_actions: (sfEP.recommended_actions || []).join('\n'),
        prefill_area: template.primary_life_area || (template.life_areas || [])[0] || '',
        from_social_learning: template.id,
      },
    });
    setDetailModal(false);
  };

  // ========================
  // RENDER: Stats Bar
  // ========================

  const renderStatsBar = () => {
    if (!stats) return null;
    return (
      <View style={styles.statsRow}>
        <View style={styles.statItem}>
          <Text style={styles.statNum}>{stats.my_templates || 0}</Text>
          <Text style={styles.statLabel}>My</Text>
        </View>
        <View style={[styles.statItem, { borderLeftWidth: 1, borderLeftColor: COLORS.border }]}>
          <Text style={[styles.statNum, { color: '#059669' }]}>{stats.tier_2_authorized || 0}</Text>
          <Text style={styles.statLabel}>Authorized</Text>
        </View>
        <View style={[styles.statItem, { borderLeftWidth: 1, borderLeftColor: COLORS.border }]}>
          <Text style={[styles.statNum, { color: '#7C3AED' }]}>{stats.tier_3_solutions || 0}</Text>
          <Text style={styles.statLabel}>Premium</Text>
        </View>
        <View style={[styles.statItem, { borderLeftWidth: 1, borderLeftColor: COLORS.border }]}>
          <Text style={[styles.statNum, { color: '#3B82F6' }]}>{stats.pending_review || 0}</Text>
          <Text style={styles.statLabel}>Pending</Text>
        </View>
      </View>
    );
  };

  // ========================
  // RENDER: Upload Tab
  // ========================

  const renderUploadTab = () => (
    <View>
      {/* Input Mode Selector */}
      <View style={styles.modeRow}>
        {INPUT_MODES.map(m => (
          <TouchableOpacity
            key={m.key}
            style={[styles.modeCard, inputMode === m.key && styles.modeCardActive]}
            onPress={() => setInputMode(m.key)}
          >
            <Ionicons
              name={m.icon as any}
              size={22}
              color={inputMode === m.key ? '#FFF' : COLORS.primary}
            />
            <Text style={[styles.modeLabel, inputMode === m.key && { color: '#FFF' }]}>
              {m.label}
            </Text>
            <Text style={[styles.modeDesc, inputMode === m.key && { color: 'rgba(255,255,255,0.7)' }]}>
              {m.desc}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Supported Languages */}
      <View style={styles.langBar}>
        <Ionicons name="language" size={14} color={COLORS.textMuted} />
        <Text style={styles.langText}>
          Supported: {LANGUAGES.map(l => l.label).join(', ')}
          {inputMode === 'audio' ? ' (Audio: English only)' : ''}
        </Text>
      </View>

      {/* Common Fields */}
      <TextInput
        style={styles.input}
        placeholder="Title (optional)"
        placeholderTextColor={COLORS.textMuted}
        value={title}
        onChangeText={setTitle}
      />

      {inputMode !== 'audio' && (
        <>
          <TextInput
            style={styles.input}
            placeholder="Source name (e.g., Times of India)"
            placeholderTextColor={COLORS.textMuted}
            value={sourceName}
            onChangeText={setSourceName}
          />
          <TextInput
            style={styles.input}
            placeholder="Source URL (optional)"
            placeholderTextColor={COLORS.textMuted}
            value={sourceUrl}
            onChangeText={setSourceUrl}
            autoCapitalize="none"
            keyboardType="url"
          />
        </>
      )}

      {/* URL Input Mode */}
      {inputMode === 'url' && (
        <>
          <View style={styles.audioInfo}>
            <Ionicons name="information-circle" size={16} color={COLORS.info} />
            <Text style={styles.audioInfoText}>
              Paste a news article URL. The content will be automatically scraped and classified. English only for now.
            </Text>
          </View>

          <TextInput
            style={styles.input}
            placeholder="https://example.com/news-article"
            placeholderTextColor={COLORS.textMuted}
            value={newsUrl}
            onChangeText={setNewsUrl}
            autoCapitalize="none"
            keyboardType="url"
            autoCorrect={false}
          />

          <TextInput
            style={styles.input}
            placeholder="Title (optional - auto-detected from page)"
            placeholderTextColor={COLORS.textMuted}
            value={title}
            onChangeText={setTitle}
          />

          <TextInput
            style={styles.input}
            placeholder="Source name (optional - auto-detected from domain)"
            placeholderTextColor={COLORS.textMuted}
            value={sourceName}
            onChangeText={setSourceName}
          />

          <TouchableOpacity
            style={[styles.uploadBtn, (uploading || !newsUrl.trim().startsWith('http')) && styles.uploadBtnDisabled]}
            onPress={handleUrlUpload}
            disabled={uploading || !newsUrl.trim().startsWith('http')}
          >
            {uploading ? (
              <ActivityIndicator color="#FFF" size="small" />
            ) : (
              <>
                <Ionicons name="link" size={18} color="#FFF" />
                <Text style={styles.uploadBtnText}>Fetch & Classify</Text>
              </>
            )}
          </TouchableOpacity>
        </>
      )}

      {/* Text Input Mode */}
      {inputMode === 'text' && (
        <>
          <TextInput
            style={styles.textArea}
            placeholder={"Paste or type the news article here (min 50 characters)...\n\nSupports English, Hindi, Tamil, Telugu, Kannada, and Malayalam"}
            placeholderTextColor={COLORS.textMuted}
            value={newsText}
            onChangeText={setNewsText}
            multiline
            numberOfLines={8}
            textAlignVertical="top"
          />
          <Text style={styles.charCount}>{newsText.length} characters</Text>

          <TouchableOpacity
            style={[styles.uploadBtn, (uploading || newsText.length < 50) && styles.uploadBtnDisabled]}
            onPress={handleTextUpload}
            disabled={uploading || newsText.length < 50}
          >
            {uploading ? (
              <ActivityIndicator color="#FFF" size="small" />
            ) : (
              <>
                <Ionicons name="sparkles" size={18} color="#FFF" />
                <Text style={styles.uploadBtnText}>Classify & Generate Template</Text>
              </>
            )}
          </TouchableOpacity>
        </>
      )}

      {/* File Input Mode */}
      {inputMode === 'file' && (
        <>
          <TouchableOpacity style={styles.filePickBtn} onPress={handleFilePick}>
            <Ionicons name="document-attach" size={28} color={COLORS.primary} />
            <Text style={styles.filePickText}>
              {selectedFile ? selectedFile.name : 'Tap to select a file'}
            </Text>
            <Text style={styles.filePickHint}>PDF, DOCX, TXT, JPG, PNG, WEBP (Max 10MB)</Text>
          </TouchableOpacity>

          {selectedFile && (
            <View style={styles.fileSelected}>
              <Ionicons name="checkmark-circle" size={16} color={COLORS.success} />
              <Text style={styles.fileSelectedText}>{selectedFile.name}</Text>
              <TouchableOpacity onPress={() => setSelectedFile(null)}>
                <Ionicons name="close-circle" size={18} color={COLORS.error} />
              </TouchableOpacity>
            </View>
          )}

          <TouchableOpacity
            style={[styles.uploadBtn, (uploading || !selectedFile) && styles.uploadBtnDisabled]}
            onPress={handleFileUpload}
            disabled={uploading || !selectedFile}
          >
            {uploading ? (
              <ActivityIndicator color="#FFF" size="small" />
            ) : (
              <>
                <Ionicons name="sparkles" size={18} color="#FFF" />
                <Text style={styles.uploadBtnText}>Extract & Classify</Text>
              </>
            )}
          </TouchableOpacity>
        </>
      )}

      {/* Audio Input Mode */}
      {inputMode === 'audio' && (
        <>
          <View style={styles.audioInfo}>
            <Ionicons name="information-circle" size={16} color={COLORS.info} />
            <Text style={styles.audioInfoText}>
              English audio/video only. Select audio (WAV, MP3, OGG, M4A) or video (MP4, MOV, AVI, MKV). Audio will be extracted from video automatically.
            </Text>
          </View>

          <TextInput
            style={styles.input}
            placeholder="Source name (e.g., News podcast)"
            placeholderTextColor={COLORS.textMuted}
            value={sourceName}
            onChangeText={setSourceName}
          />

          <TouchableOpacity
            style={[styles.uploadBtn, uploading && styles.uploadBtnDisabled]}
            onPress={handleAudioUpload}
            disabled={uploading}
          >
            {uploading ? (
              <ActivityIndicator color="#FFF" size="small" />
            ) : (
              <>
                <Ionicons name="mic" size={18} color="#FFF" />
                <Text style={styles.uploadBtnText}>Pick Audio/Video & Transcribe</Text>
              </>
            )}
          </TouchableOpacity>
        </>
      )}

      {/* Upload Processing Notice */}
      {uploading && (
        <View style={styles.processingBox}>
          <ActivityIndicator color={COLORS.primary} size="small" />
          <Text style={styles.processingText}>
            AI is analyzing the content...{'\n'}
            Detecting language, classifying, extracting factors & concerns
          </Text>
        </View>
      )}

      {/* Last Result Preview */}
      {lastResult && !uploading && (
        <View style={styles.resultCard}>
          <View style={styles.resultHeader}>
            <Ionicons name="checkmark-circle" size={20} color={COLORS.success} />
            <Text style={styles.resultTitle}>Template Created!</Text>
          </View>

          <Text style={styles.resultName}>{lastResult.title}</Text>

          <View style={styles.resultMeta}>
            {lastResult.category && (
              <View style={[styles.categoryBadge, { backgroundColor: (CATEGORY_ICONS[lastResult.category] || {}).color + '20' }]}>
                <Ionicons
                  name={(CATEGORY_ICONS[lastResult.category] || { icon: 'help' }).icon as any}
                  size={12}
                  color={(CATEGORY_ICONS[lastResult.category] || { color: '#666' }).color}
                />
                <Text style={[styles.categoryText, { color: (CATEGORY_ICONS[lastResult.category] || { color: '#666' }).color }]}>
                  {lastResult.category}
                </Text>
              </View>
            )}
            <View style={[styles.tierBadge, { backgroundColor: (TIER_LABELS[lastResult.tier] || TIER_LABELS[1]).bg }]}>
              <Text style={[styles.tierText, { color: (TIER_LABELS[lastResult.tier] || TIER_LABELS[1]).color }]}>
                {(TIER_LABELS[lastResult.tier] || TIER_LABELS[1]).label}
              </Text>
            </View>
            <Text style={styles.resultLang}>{lastResult.detected_language}</Text>
          </View>

          <Text style={styles.resultSummary}>{lastResult.english_summary}</Text>

          {(lastResult.life_areas || []).length > 0 && (
            <View style={styles.tagRow}>
              {lastResult.life_areas.map((la: string) => (
                <View key={la} style={styles.tag}>
                  <Text style={styles.tagText}>{LIFE_AREA_LABELS[la] || la}</Text>
                </View>
              ))}
            </View>
          )}

          <View style={styles.resultActions}>
            <TouchableOpacity
              style={styles.resultActionBtn}
              onPress={() => openDetail(lastResult.id)}
            >
              <Ionicons name="eye" size={14} color={COLORS.primary} />
              <Text style={styles.resultActionText}>View Details</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.resultActionBtn, { backgroundColor: '#EFF6FF' }]}
              onPress={() => handleSubmit(lastResult.id)}
            >
              <Ionicons name="send" size={14} color="#3B82F6" />
              <Text style={[styles.resultActionText, { color: '#3B82F6' }]}>Submit for Review</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );

  // ========================
  // RENDER: Template Card
  // ========================

  const renderTemplateCard = (item: any, showActions: boolean = false) => {
    const cat = CATEGORY_ICONS[item.category] || { icon: 'help', color: '#666' };
    const tier = TIER_LABELS[item.tier] || TIER_LABELS[1];
    const status = STATUS_COLORS[item.status] || STATUS_COLORS.draft;

    return (
      <TouchableOpacity
        key={item.id}
        style={styles.templateCard}
        onPress={() => openDetail(item.id, item.tier === 3)}
        activeOpacity={0.7}
      >
        <View style={styles.templateHeader}>
          <View style={[styles.categoryBadge, { backgroundColor: cat.color + '20' }]}>
            <Ionicons name={cat.icon as any} size={12} color={cat.color} />
            <Text style={[styles.categoryText, { color: cat.color }]}>
              {item.category}
            </Text>
          </View>
          <View style={[styles.tierBadge, { backgroundColor: tier.bg }]}>
            <Text style={[styles.tierText, { color: tier.color }]}>{tier.label}</Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: status.bg }]}>
            <Text style={[styles.statusText, { color: status.color }]}>{item.status}</Text>
          </View>
        </View>

        <Text style={styles.templateTitle} numberOfLines={2}>{item.title}</Text>
        <Text style={styles.templateSummary} numberOfLines={2}>
          {item.english_summary || item.description || ''}
        </Text>

        {(item.life_areas || []).length > 0 && (
          <View style={styles.miniTagRow}>
            {(item.life_areas || []).slice(0, 3).map((la: string) => (
              <View key={la} style={styles.miniTag}>
                <Text style={styles.miniTagText}>{LIFE_AREA_LABELS[la] || la}</Text>
              </View>
            ))}
          </View>
        )}

        {item.severity_score && (
          <View style={styles.severityRow}>
            <Text style={styles.severityLabel}>Severity:</Text>
            <View style={styles.severityBar}>
              <View style={[styles.severityFill, {
                width: `${(item.severity_score / 10) * 100}%`,
                backgroundColor: item.severity_score >= 7 ? '#EF4444' : item.severity_score >= 4 ? '#F59E0B' : '#10B981',
              }]} />
            </View>
            <Text style={styles.severityScore}>{item.severity_score}/10</Text>
          </View>
        )}

        {showActions && item.status === 'draft' && (
          <View style={styles.cardActions}>
            <TouchableOpacity
              style={styles.actionChip}
              onPress={(e) => { e.stopPropagation(); handleSubmit(item.id); }}
            >
              <Ionicons name="send" size={12} color="#3B82F6" />
              <Text style={[styles.actionChipText, { color: '#3B82F6' }]}>Submit</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionChip, { backgroundColor: '#FEF2F2' }]}
              onPress={(e) => { e.stopPropagation(); handleDelete(item.id); }}
            >
              <Ionicons name="trash" size={12} color="#EF4444" />
              <Text style={[styles.actionChipText, { color: '#EF4444' }]}>Delete</Text>
            </TouchableOpacity>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  // ========================
  // RENDER: My Templates Tab
  // ========================

  const renderMyTemplatesTab = () => (
    <View>
      <View style={styles.filterRow}>
        {['all', 'draft', 'submitted', 'authorized', 'rejected'].map(f => (
          <TouchableOpacity
            key={f}
            style={[styles.filterChip, myFilter === f && styles.filterChipActive]}
            onPress={() => { setMyFilter(f); }}
          >
            <Text style={[styles.filterChipText, myFilter === f && styles.filterChipTextActive]}>
              {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {myLoading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      ) : myTemplates.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="document-text-outline" size={48} color={COLORS.textMuted} />
          <Text style={styles.emptyTitle}>No templates yet</Text>
          <Text style={styles.emptyText}>Upload news to create your first template</Text>
          <TouchableOpacity style={styles.emptyBtn} onPress={() => setActiveTab('upload')}>
            <Text style={styles.emptyBtnText}>Upload News</Text>
          </TouchableOpacity>
        </View>
      ) : (
        myTemplates.map(t => renderTemplateCard(t, true))
      )}
    </View>
  );

  // ========================
  // RENDER: Browse Tab (Authorized)
  // ========================

  const renderBrowseTab = () => (
    <View>
      <TextInput
        style={styles.searchInput}
        placeholder="Search templates..."
        placeholderTextColor={COLORS.textMuted}
        value={browseSearch}
        onChangeText={setBrowseSearch}
        onSubmitEditing={fetchAuthorized}
        returnKeyType="search"
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
        <TouchableOpacity
          style={[styles.filterChip, browseFilter === '' && styles.filterChipActive]}
          onPress={() => setBrowseFilter('')}
        >
          <Text style={[styles.filterChipText, browseFilter === '' && styles.filterChipTextActive]}>All Areas</Text>
        </TouchableOpacity>
        {Object.entries(LIFE_AREA_LABELS).map(([key, label]) => (
          <TouchableOpacity
            key={key}
            style={[styles.filterChip, browseFilter === key && styles.filterChipActive]}
            onPress={() => setBrowseFilter(key)}
          >
            <Text style={[styles.filterChipText, browseFilter === key && styles.filterChipTextActive]}
              numberOfLines={1}>
              {label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {browseLoading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      ) : authorizedTemplates.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="globe-outline" size={48} color={COLORS.textMuted} />
          <Text style={styles.emptyTitle}>No authorized templates</Text>
          <Text style={styles.emptyText}>Community-verified templates will appear here</Text>
        </View>
      ) : (
        authorizedTemplates.map(t => renderTemplateCard(t))
      )}
    </View>
  );

  // ========================
  // RENDER: Premium Tab
  // ========================

  const renderPremiumTab = () => (
    <View>
      <View style={styles.premiumBanner}>
        <LinearGradient colors={['#7C3AED', '#5B21B6']} style={styles.premiumGradient}>
          <Ionicons name="diamond" size={24} color="#FFF" />
          <Text style={styles.premiumTitle}>AI-Synthesized Intelligence</Text>
          <Text style={styles.premiumSubtext}>
            Premium templates distilled from multiple verified sources
          </Text>
        </LinearGradient>
      </View>

      {premiumLoading ? (
        <ActivityIndicator size="large" color="#7C3AED" style={{ marginTop: 40 }} />
      ) : premiumSolutions.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="diamond-outline" size={48} color={COLORS.textMuted} />
          <Text style={styles.emptyTitle}>No premium solutions yet</Text>
          <Text style={styles.emptyText}>AI-synthesized templates from verified sources will appear here</Text>
        </View>
      ) : (
        premiumSolutions.map(s => renderTemplateCard({ ...s, tier: 3 }))
      )}
    </View>
  );

  // ========================
  // RENDER: Detail Modal
  // ========================

  const renderDetailModal = () => {
    const t = selectedTemplate;
    if (!t) return null;

    const scenario = t.life_scenario_template || t.premium_life_scenario || {};
    const decisionEP = scenario.decision_entry_point || {};
    const sfEP = scenario.solution_finder_entry_point || {};
    const isSolution = t._isSolution || t.tier === 3;

    return (
      <Modal visible={detailModal} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={styles.modalContainer} edges={['top']}>
          {/* Modal Header */}
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setDetailModal(false)} style={styles.modalClose}>
              <Ionicons name="close" size={24} color={COLORS.textPrimary} />
            </TouchableOpacity>
            <Text style={styles.modalHeaderTitle} numberOfLines={1}>Template Detail</Text>
            <View style={{ width: 40 }} />
          </View>

          {detailLoading ? (
            <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 80 }} />
          ) : (
            <ScrollView style={styles.modalScroll} contentContainerStyle={{ paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
              {/* Title & Meta */}
              <Text style={styles.detailTitle}>{t.title}</Text>

              <View style={styles.detailMetaRow}>
                {t.category && (
                  <View style={[styles.categoryBadge, { backgroundColor: (CATEGORY_ICONS[t.category] || { color: '#666' }).color + '20' }]}>
                    <Ionicons
                      name={(CATEGORY_ICONS[t.category] || { icon: 'help' }).icon as any}
                      size={12}
                      color={(CATEGORY_ICONS[t.category] || { color: '#666' }).color}
                    />
                    <Text style={[styles.categoryText, { color: (CATEGORY_ICONS[t.category] || { color: '#666' }).color }]}>
                      {t.category}
                    </Text>
                  </View>
                )}
                <View style={[styles.tierBadge, { backgroundColor: (TIER_LABELS[t.tier] || TIER_LABELS[1]).bg }]}>
                  <Text style={[styles.tierText, { color: (TIER_LABELS[t.tier] || TIER_LABELS[1]).color }]}>
                    Tier {t.tier}: {(TIER_LABELS[t.tier] || TIER_LABELS[1]).label}
                  </Text>
                </View>
                {t.detected_language && (
                  <View style={styles.langBadge}>
                    <Text style={styles.langBadgeText}>{t.detected_language}</Text>
                  </View>
                )}
              </View>

              {/* Summary */}
              {(t.english_summary || t.description) && (
                <View style={styles.detailSection}>
                  <Text style={styles.detailSectionTitle}>Summary</Text>
                  <Text style={styles.detailText}>{t.english_summary || t.description}</Text>
                </View>
              )}

              {/* Life Areas */}
              {(t.life_areas || []).length > 0 && (
                <View style={styles.detailSection}>
                  <Text style={styles.detailSectionTitle}>Life Areas</Text>
                  <View style={styles.tagRow}>
                    {t.life_areas.map((la: string) => (
                      <View key={la} style={styles.tag}>
                        <Text style={styles.tagText}>{LIFE_AREA_LABELS[la] || la}</Text>
                      </View>
                    ))}
                  </View>
                  {t.life_area_sub_area && (
                    <Text style={styles.subAreaText}>Sub-area: {t.life_area_sub_area}</Text>
                  )}
                </View>
              )}

              {/* Factors */}
              {((t.factors || t.synthesized_factors || []).length > 0) && (
                <View style={styles.detailSection}>
                  <Text style={styles.detailSectionTitle}>
                    {isSolution ? 'Synthesized Factors' : 'Extracted Factors'}
                  </Text>
                  {(t.factors || t.synthesized_factors || []).map((f: any, i: number) => (
                    <View key={i} style={styles.factorCard}>
                      <View style={styles.factorHeader}>
                        <Text style={styles.factorName}>{f.name}</Text>
                        <View style={[styles.priorityBadge, {
                          backgroundColor: f.priority >= 7 ? '#FEF2F2' : f.priority >= 4 ? '#FFFBEB' : '#ECFDF5',
                        }]}>
                          <Text style={[styles.priorityText, {
                            color: f.priority >= 7 ? '#EF4444' : f.priority >= 4 ? '#D97706' : '#059669',
                          }]}>
                            P{f.priority}
                          </Text>
                        </View>
                      </View>
                      {f.description && <Text style={styles.factorDesc}>{f.description}</Text>}
                    </View>
                  ))}
                </View>
              )}

              {/* Concerns */}
              {((t.concerns || t.synthesized_concerns || []).length > 0) && (
                <View style={styles.detailSection}>
                  <Text style={styles.detailSectionTitle}>
                    {isSolution ? 'Synthesized Concerns' : 'Concerns'}
                  </Text>
                  {(t.concerns || t.synthesized_concerns || []).map((c: any, i: number) => (
                    <View key={i} style={styles.concernCard}>
                      <View style={styles.concernHeader}>
                        <Ionicons name="alert-circle" size={14} color={
                          c.severity === 'high' ? '#EF4444' : c.severity === 'medium' ? '#F59E0B' : '#10B981'
                        } />
                        <Text style={styles.concernText}>{c.concern}</Text>
                      </View>
                      {c.mitigation && (
                        <Text style={styles.mitigationText}>Mitigation: {c.mitigation || c.mitigation_consensus}</Text>
                      )}
                    </View>
                  ))}
                </View>
              )}

              {/* Root Causes */}
              {((t.root_causes || t.combined_root_causes || []).length > 0) && (
                <View style={styles.detailSection}>
                  <Text style={styles.detailSectionTitle}>Root Causes</Text>
                  {(t.root_causes || t.combined_root_causes || []).map((rc: string, i: number) => (
                    <View key={i} style={styles.listItem}>
                      <Text style={styles.listBullet}>{i + 1}.</Text>
                      <Text style={styles.listText}>{rc}</Text>
                    </View>
                  ))}
                </View>
              )}

              {/* Lessons Learned */}
              {((t.lessons_learned || t.combined_lessons || []).length > 0) && (
                <View style={styles.detailSection}>
                  <Text style={styles.detailSectionTitle}>Lessons Learned</Text>
                  {(t.lessons_learned || t.combined_lessons || []).map((l: string, i: number) => (
                    <View key={i} style={styles.listItem}>
                      <Ionicons name="bulb" size={14} color="#F59E0B" />
                      <Text style={styles.listText}>{l}</Text>
                    </View>
                  ))}
                </View>
              )}

              {/* Life Scenario Template - Decision Entry */}
              {decisionEP.problem_statement && (
                <View style={[styles.detailSection, styles.scenarioSection]}>
                  <Text style={[styles.detailSectionTitle, { color: COLORS.primary }]}>
                    Decision Entry Point
                  </Text>
                  <Text style={styles.detailText}>{decisionEP.problem_statement}</Text>

                  {(decisionEP.key_factors || []).length > 0 && (
                    <View style={{ marginTop: 8 }}>
                      <Text style={styles.subSectionTitle}>Key Factors:</Text>
                      {decisionEP.key_factors.map((f: string, i: number) => (
                        <Text key={i} style={styles.bulletText}>• {f}</Text>
                      ))}
                    </View>
                  )}

                  {(decisionEP.options_to_evaluate || []).length > 0 && (
                    <View style={{ marginTop: 8 }}>
                      <Text style={styles.subSectionTitle}>Options to Evaluate:</Text>
                      {decisionEP.options_to_evaluate.map((o: string, i: number) => (
                        <Text key={i} style={styles.bulletText}>• {o}</Text>
                      ))}
                    </View>
                  )}
                </View>
              )}

              {/* Solution Finder Entry */}
              {sfEP.smart_goal && (
                <View style={[styles.detailSection, styles.scenarioSection]}>
                  <Text style={[styles.detailSectionTitle, { color: '#059669' }]}>
                    Solution Finder Entry Point
                  </Text>
                  <Text style={styles.detailText}>Goal: {sfEP.smart_goal}</Text>

                  {(sfEP.main_concerns || []).length > 0 && (
                    <View style={{ marginTop: 8 }}>
                      <Text style={styles.subSectionTitle}>Main Concerns:</Text>
                      {sfEP.main_concerns.map((c: string, i: number) => (
                        <Text key={i} style={styles.bulletText}>• {c}</Text>
                      ))}
                    </View>
                  )}

                  {(sfEP.risk_management_questions || []).length > 0 && (
                    <View style={{ marginTop: 8 }}>
                      <Text style={styles.subSectionTitle}>Risk Questions (Q4):</Text>
                      {sfEP.risk_management_questions.map((q: string, i: number) => (
                        <Text key={i} style={styles.bulletText}>• {q}</Text>
                      ))}
                    </View>
                  )}
                </View>
              )}

              {/* Action Buttons */}
              <View style={styles.detailActions}>
                {(t.tier === 2 || t.tier === 3) && (
                  <>
                    <TouchableOpacity
                      style={styles.useDecisionBtn}
                      onPress={() => handleUseInDecision(t)}
                    >
                      <Ionicons name="git-branch" size={16} color="#FFF" />
                      <Text style={styles.useBtnText}>Use in My Dezider</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.useSolutionBtn}
                      onPress={() => handleUseInSolutionFinder(t)}
                    >
                      <Ionicons name="bulb" size={16} color="#FFF" />
                      <Text style={styles.useBtnText}>Use in Solution Finder</Text>
                    </TouchableOpacity>
                  </>
                )}
                {t.status === 'draft' && (
                  <TouchableOpacity
                    style={styles.submitBtn}
                    onPress={() => { handleSubmit(t.id); setDetailModal(false); }}
                  >
                    <Ionicons name="send" size={16} color="#FFF" />
                    <Text style={styles.useBtnText}>Submit for Review</Text>
                  </TouchableOpacity>
                )}
              </View>
            </ScrollView>
          )}
        </SafeAreaView>
      </Modal>
    );
  };

  // ========================
  // MAIN RENDER
  // ========================

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        {/* Header */}
        <LinearGradient colors={GRADIENTS.header} style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>Social Learning</Text>
            <Text style={styles.headerSub}>News → Intelligence → Action</Text>
          </View>
        </LinearGradient>

        {/* Stats */}
        {renderStatsBar()}

        {/* Tab Bar */}
        <View style={styles.tabBar}>
          {TABS.map(tab => (
            <TouchableOpacity
              key={tab.key}
              style={[styles.tab, activeTab === tab.key && styles.tabActive]}
              onPress={() => setActiveTab(tab.key)}
            >
              <Ionicons
                name={tab.icon as any}
                size={18}
                color={activeTab === tab.key ? COLORS.primary : COLORS.textMuted}
              />
              <Text style={[styles.tabText, activeTab === tab.key && styles.tabTextActive]}>
                {tab.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Content */}
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
        >
          {activeTab === 'upload' && renderUploadTab()}
          {activeTab === 'my' && renderMyTemplatesTab()}
          {activeTab === 'browse' && renderBrowseTab()}
          {activeTab === 'premium' && renderPremiumTab()}
        </ScrollView>

        {/* Detail Modal */}
        {renderDetailModal()}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ========================
// STYLES
// ========================

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    paddingBottom: 20,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
    marginRight: 12,
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },

  // Stats
  statsRow: {
    flexDirection: 'row', backgroundColor: '#FFF',
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  statItem: { flex: 1, alignItems: 'center' },
  statNum: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  statLabel: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },

  // Tabs
  tabBar: {
    flexDirection: 'row', backgroundColor: '#FFF',
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  tab: {
    flex: 1, alignItems: 'center', paddingVertical: 10, gap: 2,
  },
  tabActive: { borderBottomWidth: 2, borderBottomColor: COLORS.primary },
  tabText: { fontSize: 11, color: COLORS.textMuted, fontWeight: '500' },
  tabTextActive: { color: COLORS.primary, fontWeight: '600' },

  // Content
  scrollView: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 40 },

  // Input Mode
  modeRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  modeCard: {
    flex: 1, alignItems: 'center', padding: 12, borderRadius: 12,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.border, gap: 4,
  },
  modeCardActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  modeLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  modeDesc: { fontSize: 9, color: COLORS.textMuted, textAlign: 'center' },

  // Language bar
  langBar: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 6, backgroundColor: '#F0F0FF',
    borderRadius: 8, marginBottom: 12,
  },
  langText: { fontSize: 11, color: COLORS.textMuted },

  // Inputs
  input: {
    backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary,
    marginBottom: 8,
  },
  textArea: {
    backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 12, fontSize: 14, color: COLORS.textPrimary,
    minHeight: 160, textAlignVertical: 'top', marginBottom: 4,
  },
  charCount: { fontSize: 11, color: COLORS.textMuted, textAlign: 'right', marginBottom: 12 },

  // Upload button
  uploadBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 14, marginTop: 8,
  },
  uploadBtnDisabled: { opacity: 0.5 },
  uploadBtnText: { fontSize: 15, fontWeight: '600', color: '#FFF' },

  // File pick
  filePickBtn: {
    alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 2, borderColor: COLORS.border, borderStyle: 'dashed',
    borderRadius: 12, paddingVertical: 30, backgroundColor: '#FAFBFC',
    marginBottom: 8,
  },
  filePickText: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  filePickHint: { fontSize: 11, color: COLORS.textMuted },
  fileSelected: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#ECFDF5', borderRadius: 8, padding: 10, marginBottom: 8,
  },
  fileSelectedText: { flex: 1, fontSize: 13, color: '#059669', fontWeight: '500' },

  // Audio
  audioInfo: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#EFF6FF', borderRadius: 8, padding: 12, marginBottom: 12,
  },
  audioInfoText: { flex: 1, fontSize: 12, color: '#3B82F6' },

  // Processing
  processingBox: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#F5F3FF', borderRadius: 12, padding: 16, marginTop: 12,
  },
  processingText: { flex: 1, fontSize: 12, color: '#7C3AED', lineHeight: 18 },

  // Result Card
  resultCard: {
    backgroundColor: '#FFF', borderRadius: 12, padding: 16, marginTop: 16,
    borderWidth: 1, borderColor: '#D1FAE5',
  },
  resultHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  resultTitle: { fontSize: 16, fontWeight: '700', color: COLORS.success },
  resultName: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 8 },
  resultMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  resultLang: { fontSize: 11, color: COLORS.textMuted, paddingTop: 3 },
  resultSummary: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18, marginBottom: 8 },
  resultActions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  resultActionBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#F5F3FF', paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 8,
  },
  resultActionText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },

  // Badges
  categoryBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12,
  },
  categoryText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  tierBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  tierText: { fontSize: 11, fontWeight: '600' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  statusText: { fontSize: 10, fontWeight: '600', textTransform: 'capitalize' },
  langBadge: { backgroundColor: '#F3F4F6', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  langBadgeText: { fontSize: 11, color: COLORS.textMuted, textTransform: 'capitalize' },

  // Tags
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  tag: { backgroundColor: '#F0E6FF', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  tagText: { fontSize: 10, color: '#7C3AED', fontWeight: '500' },
  miniTagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 6 },
  miniTag: { backgroundColor: '#F3F4F6', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  miniTagText: { fontSize: 9, color: COLORS.textMuted },

  // Severity
  severityRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  severityLabel: { fontSize: 11, color: COLORS.textMuted },
  severityBar: { flex: 1, height: 4, backgroundColor: '#F3F4F6', borderRadius: 2 },
  severityFill: { height: '100%', borderRadius: 2 },
  severityScore: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },

  // Template Card
  templateCard: {
    backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: COLORS.border,
  },
  templateHeader: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  templateTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  templateSummary: { fontSize: 12, color: COLORS.textSecondary, lineHeight: 17 },
  cardActions: { flexDirection: 'row', gap: 8, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: COLORS.border },
  actionChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8,
    backgroundColor: '#EFF6FF',
  },
  actionChipText: { fontSize: 11, fontWeight: '600' },

  // Filters
  filterRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 14 },
  filterScroll: { marginBottom: 14 },
  filterChip: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.border, marginRight: 6,
  },
  filterChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  filterChipText: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '500' },
  filterChipTextActive: { color: '#FFF' },

  // Search
  searchInput: {
    backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary,
    marginBottom: 10,
  },

  // Empty
  emptyState: { alignItems: 'center', paddingTop: 40, gap: 8 },
  emptyTitle: { fontSize: 16, fontWeight: '600', color: COLORS.textSecondary },
  emptyText: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center' },
  emptyBtn: {
    backgroundColor: COLORS.primary, paddingHorizontal: 20, paddingVertical: 10,
    borderRadius: 10, marginTop: 12,
  },
  emptyBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },

  // Premium
  premiumBanner: { marginBottom: 16, borderRadius: 12, overflow: 'hidden' },
  premiumGradient: { alignItems: 'center', padding: 20, gap: 8 },
  premiumTitle: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  premiumSubtext: { fontSize: 12, color: 'rgba(255,255,255,0.8)', textAlign: 'center' },

  // Detail Modal
  modalContainer: { flex: 1, backgroundColor: COLORS.background },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#FFF',
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  modalClose: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center' },
  modalHeaderTitle: { fontSize: 16, fontWeight: '600', color: COLORS.textPrimary },
  modalScroll: { flex: 1, padding: 16 },

  detailTitle: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  detailMetaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  detailSection: {
    backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: COLORS.border,
  },
  scenarioSection: { borderColor: '#E0D4FF', backgroundColor: '#FDFBFF' },
  detailSectionTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  detailText: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19 },
  subAreaText: { fontSize: 12, color: COLORS.primary, marginTop: 6, fontStyle: 'italic' },

  // Factors
  factorCard: {
    backgroundColor: '#F9FAFB', borderRadius: 8, padding: 10, marginBottom: 6,
  },
  factorHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  factorName: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, flex: 1 },
  factorDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 4 },
  priorityBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  priorityText: { fontSize: 10, fontWeight: '700' },

  // Concerns
  concernCard: { backgroundColor: '#FFFBEB', borderRadius: 8, padding: 10, marginBottom: 6 },
  concernHeader: { flexDirection: 'row', gap: 6, alignItems: 'flex-start' },
  concernText: { flex: 1, fontSize: 12, color: COLORS.textPrimary },
  mitigationText: { fontSize: 11, color: '#059669', marginTop: 4, paddingLeft: 20 },

  // Lists
  listItem: { flexDirection: 'row', gap: 6, marginBottom: 4, alignItems: 'flex-start' },
  listBullet: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted, width: 16 },
  listText: { flex: 1, fontSize: 12, color: COLORS.textSecondary, lineHeight: 17 },
  subSectionTitle: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  bulletText: { fontSize: 12, color: COLORS.textSecondary, lineHeight: 18, paddingLeft: 4 },

  // Detail Actions
  detailActions: { gap: 10, marginTop: 8 },
  useDecisionBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 14,
  },
  useSolutionBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#059669', borderRadius: 12, paddingVertical: 14,
  },
  submitBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#3B82F6', borderRadius: 12, paddingVertical: 14,
  },
  useBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
});
