import React, { useState, useCallback, useRef, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
  FlatList,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import * as Speech from 'expo-speech';
import { safeBack } from '../../src/utils/navigation';

const LANGS = [
  { id: 'en', name: 'English', flag: '🇬🇧' },
  { id: 'ta', name: 'Tamil', flag: '🇮🇳' },
  { id: 'te', name: 'Telugu', flag: '🇮🇳' },
  { id: 'kn', name: 'Kannada', flag: '🇮🇳' },
  { id: 'ml', name: 'Malayalam', flag: '🇮🇳' },
  { id: 'hi', name: 'Hindi', flag: '🇮🇳' },
];

const LANG_CODES: Record<string, string> = {
  en: 'en-US', ta: 'ta-IN', te: 'te-IN', kn: 'kn-IN', ml: 'ml-IN', hi: 'hi-IN',
};

export default function AIAssistantScreen() {
  const router = useRouter();
  const scrollRef = useRef<ScrollView>(null);
  const [loading, setLoading] = useState(true);
  const [conversations, setConversations] = useState<any[]>([]);
  const [activeConv, setActiveConv] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [selectedLang, setSelectedLang] = useState('en');
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);

  const fetchConversations = async () => {
    try {
      const res = await api.get('/ai-assistant/conversations');
      setConversations(res.data || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchConversations(); }, []));

  const openConversation = async (conv: any) => {
    try {
      const res = await api.get(`/ai-assistant/conversations/${conv.conversation_id}`);
      setActiveConv(res.data);
      setMessages(res.data.messages || []);
      setSelectedLang(res.data.language || 'en');
    } catch (e) { showAlert('Error', 'Failed to open conversation'); }
  };

  const createConversation = async () => {
    try {
      const res = await api.post('/ai-assistant/conversations', {
        title: 'New Conversation',
        language: selectedLang,
      });
      setActiveConv(res.data);
      setMessages([]);
    } catch (e) { showAlert('Error', 'Failed to create'); }
  };

  const deleteConversation = (cid: string) => {
    showAlert('Delete', 'Delete this conversation?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try {
          await api.delete(`/ai-assistant/conversations/${cid}`);
          fetchConversations();
          if (activeConv?.conversation_id === cid) { setActiveConv(null); setMessages([]); }
        } catch (e) { showAlert('Error', 'Failed'); }
      }},
    ]);
  };

  const sendMessage = async () => {
    if (!inputText.trim() || !activeConv) return;
    const msg = inputText.trim();
    setInputText('');
    setSending(true);

    // Optimistic UI
    setMessages(prev => [...prev, { role: 'user', content: msg, timestamp: new Date().toISOString() }]);
    setTimeout(() => scrollRef.current?.scrollToEnd?.({ animated: true }), 100);

    try {
      const res = await api.post(`/ai-assistant/conversations/${activeConv.conversation_id}/message`, {
        message: msg,
      });
      const aiMsg = { role: 'assistant', content: res.data.ai_response, timestamp: res.data.timestamp };
      setMessages(prev => [...prev, aiMsg]);
      setTimeout(() => scrollRef.current?.scrollToEnd?.({ animated: true }), 100);

      // TTS
      if (ttsEnabled) {
        speakText(res.data.ai_response);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.', timestamp: new Date().toISOString() }]);
    }
    finally { setSending(false); }
  };

  const speakText = async (text: string) => {
    try {
      await Speech.stop();
      setIsSpeaking(true);
      Speech.speak(text, {
        language: LANG_CODES[selectedLang] || 'en-US',
        rate: 0.9,
        onDone: () => setIsSpeaking(false),
        onError: () => setIsSpeaking(false),
      });
    } catch (e) {
      setIsSpeaking(false);
    }
  };

  const stopSpeaking = async () => {
    await Speech.stop();
    setIsSpeaking(false);
  };

  // ─── RENDER ────────────────────────────────────────────

  const renderConversationList = () => (
    <>
      <LinearGradient colors={['#FFFFFF', '#F8FAFC']} style={s.heroBanner}>
        <Ionicons name="chatbubble-ellipses" size={32} color="#818CF8" />
        <View style={{ marginLeft: 12, flex: 1 }}>
          <Text style={s.heroTitle}>AI Solution Assistant</Text>
          <Text style={s.heroSub}>Your personal advisor across all life areas and modules</Text>
        </View>
      </LinearGradient>

      {/* Language Selector */}
      <View style={s.langRow}>
        <Text style={s.langLabel}>Language:</Text>
        {LANGS.map(l => (
          <TouchableOpacity key={l.id}
            style={[s.langChip, selectedLang === l.id && s.langChipActive]}
            onPress={() => setSelectedLang(l.id)}>
            <Text style={[s.langChipText, selectedLang === l.id && { color: '#FFF' }]}>
              {l.flag} {l.name}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* New Chat Button */}
      <TouchableOpacity style={s.newChatBtn} onPress={createConversation}>
        <Ionicons name="add-circle" size={22} color="#FFF" />
        <Text style={s.newChatText}>Start New Conversation</Text>
      </TouchableOpacity>

      {/* Conversation List */}
      <Text style={s.sectionTitle}>Recent Conversations</Text>
      {conversations.length === 0 ? (
        <View style={s.emptyState}>
          <Ionicons name="chatbubbles-outline" size={48} color="#6B7280" />
          <Text style={s.emptyText}>No conversations yet</Text>
          <Text style={s.emptySub}>Start a chat to get personalized advice based on your data</Text>
        </View>
      ) : (
        conversations.map(conv => (
          <TouchableOpacity key={conv.conversation_id} style={s.convCard}
            onPress={() => openConversation(conv)}>
            <View style={s.convIcon}>
              <Ionicons name="chatbubble" size={18} color="#818CF8" />
            </View>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={s.convTitle} numberOfLines={1}>{conv.title}</Text>
              <Text style={s.convSub}>{conv.message_count} messages · {LANGS.find(l => l.id === conv.language)?.name || 'English'}</Text>
            </View>
            <TouchableOpacity onPress={() => deleteConversation(conv.conversation_id)} style={{ padding: 8 }}>
              <Ionicons name="trash-outline" size={16} color="#EF4444" />
            </TouchableOpacity>
          </TouchableOpacity>
        ))
      )}

      {/* Quick CLD Generate */}
      <Text style={[s.sectionTitle, { marginTop: 20 }]}>Quick Actions</Text>
      <View style={s.quickRow}>
        <TouchableOpacity style={s.quickCard} onPress={() => router.push('/tools/cld-engine' as any)}>
          <Ionicons name="git-network" size={22} color="#10B981" />
          <Text style={s.quickText}>View CLD</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.quickCard} onPress={() => router.push('/tools/pna' as any)}>
          <Ionicons name="layers" size={22} color="#818CF8" />
          <Text style={s.quickText}>PNA Items</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.quickCard} onPress={() => router.push('/tools/conflict-breaker' as any)}>
          <Ionicons name="flash" size={22} color="#F97316" />
          <Text style={s.quickText}>Conflicts</Text>
        </TouchableOpacity>
      </View>
    </>
  );

  const renderChatView = () => (
    <>
      {/* Chat Header */}
      <View style={s.chatHeader}>
        <View style={{ flex: 1 }}>
          <Text style={s.chatTitle} numberOfLines={1}>{activeConv?.title || 'Chat'}</Text>
          <Text style={s.chatLang}>{LANGS.find(l => l.id === selectedLang)?.name || 'English'}</Text>
        </View>
        <TouchableOpacity onPress={() => setTtsEnabled(!ttsEnabled)} style={s.ttsBtn}>
          <Ionicons name={ttsEnabled ? 'volume-high' : 'volume-mute'} size={20}
            color={ttsEnabled ? '#10B981' : '#6B7280'} />
        </TouchableOpacity>
        {isSpeaking && (
          <TouchableOpacity onPress={stopSpeaking} style={s.stopBtn}>
            <Ionicons name="stop-circle" size={20} color="#EF4444" />
          </TouchableOpacity>
        )}
      </View>

      {/* Messages */}
      <ScrollView ref={scrollRef} style={s.chatMessages}
        contentContainerStyle={{ paddingBottom: 16 }}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd?.({ animated: false })}>

        {messages.length === 0 && (
          <View style={s.welcomeMsg}>
            <Ionicons name="sparkles" size={32} color="#818CF8" />
            <Text style={s.welcomeTitle}>How can I help you today?</Text>
            <Text style={s.welcomeSub}>I have access to your PNA items, goals, conflicts, lifestyle data, and more. Ask me anything!</Text>
            <View style={s.suggestionRow}>
              {[
                'What should I focus on today?',
                'Help me with my top problem',
                'How are my goals progressing?',
              ].map((sug, i) => (
                <TouchableOpacity key={i} style={s.sugChip}
                  onPress={() => { setInputText(sug); }}>
                  <Text style={s.sugText}>{sug}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        {messages.map((msg, i) => (
          <View key={i} style={[s.msgBubble, msg.role === 'user' ? s.userBubble : s.aiBubble]}>
            {msg.role === 'assistant' && (
              <View style={s.aiAvatar}>
                <Ionicons name="sparkles" size={14} color="#818CF8" />
              </View>
            )}
            <View style={[s.msgContent, msg.role === 'user' ? s.userContent : s.aiContent]}>
              <Text style={[s.msgText, msg.role === 'user' && { color: '#FFF' }]}>{msg.content}</Text>
            </View>
            {msg.role === 'assistant' && (
              <TouchableOpacity style={s.speakBtn} onPress={() => speakText(msg.content)}>
                <Ionicons name="volume-medium" size={16} color="#818CF8" />
              </TouchableOpacity>
            )}
          </View>
        ))}

        {sending && (
          <View style={[s.msgBubble, s.aiBubble]}>
            <View style={s.aiAvatar}>
              <Ionicons name="sparkles" size={14} color="#818CF8" />
            </View>
            <View style={s.aiContent}>
              <ActivityIndicator size="small" color="#818CF8" />
              <Text style={[s.msgText, { marginLeft: 8 }]}>Thinking...</Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Input Bar */}
      <View style={s.inputBar}>
        <TextInput
          style={s.chatInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder={`Ask me anything in ${LANGS.find(l => l.id === selectedLang)?.name || 'English'}...`}
          placeholderTextColor="#6B7280"
          multiline
          maxLength={2000}
        />
        <TouchableOpacity
          style={[s.sendBtn, (!inputText.trim() || sending) && { opacity: 0.4 }]}
          onPress={sendMessage}
          disabled={!inputText.trim() || sending}>
          {sending ? <ActivityIndicator size="small" color="#FFF" /> : (
            <Ionicons name="send" size={20} color="#FFF" />
          )}
        </TouchableOpacity>
      </View>
    </>
  );

  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 20}
      >
        {/* Header */}
        <View style={s.header}>
          <TouchableOpacity onPress={() => {
            if (activeConv) { setActiveConv(null); setMessages([]); fetchConversations(); Speech.stop(); }
            else { safeBack(router); }
          }}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <Text style={s.headerTitle}>
            {activeConv ? 'AI Assistant' : 'AI Solution Assistant'}
          </Text>
          {!activeConv && (
            <TouchableOpacity onPress={createConversation}>
              <Ionicons name="add-circle" size={28} color="#FFF" />
            </TouchableOpacity>
          )}
        </View>

        {!activeConv ? (
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 100 }}>
            {renderConversationList()}
          </ScrollView>
        ) : (
          <View style={{ flex: 1, paddingHorizontal: 16 }}>
            {renderChatView()}
          </View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, paddingBottom: 8 },
  headerTitle: { color: '#0F172A', fontSize: 18, fontWeight: '700', flex: 1, marginLeft: 12 },
  heroBanner: { borderRadius: 16, padding: 16, flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  heroTitle: { color: '#0F172A', fontSize: 17, fontWeight: '700' },
  heroSub: { color: '#94A3B8', fontSize: 12, marginTop: 4 },

  // Language
  langRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginBottom: 16 },
  langLabel: { color: '#94A3B8', fontSize: 12, fontWeight: '600', marginRight: 4 },
  langChip: { borderRadius: 8, borderWidth: 1, borderColor: '#334155', paddingHorizontal: 10, paddingVertical: 5 },
  langChipActive: { backgroundColor: '#6366F1', borderColor: '#6366F1' },
  langChipText: { color: '#94A3B8', fontSize: 11, fontWeight: '500' },

  newChatBtn: { backgroundColor: '#6366F1', borderRadius: 12, paddingVertical: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 20 },
  newChatText: { color: '#0F172A', fontSize: 15, fontWeight: '700' },

  sectionTitle: { color: '#0F172A', fontSize: 16, fontWeight: '700', marginBottom: 12 },

  emptyState: { alignItems: 'center', paddingVertical: 30 },
  emptyText: { color: '#9CA3AF', fontSize: 16, fontWeight: '600', marginTop: 12 },
  emptySub: { color: '#6B7280', fontSize: 13, marginTop: 4, textAlign: 'center' },

  convCard: { backgroundColor: '#FFFFFF', borderRadius: 12, padding: 14, flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  convIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#818CF820', justifyContent: 'center', alignItems: 'center' },
  convTitle: { color: '#0F172A', fontSize: 14, fontWeight: '600' },
  convSub: { color: '#6B7280', fontSize: 11, marginTop: 2 },

  quickRow: { flexDirection: 'row', gap: 8 },
  quickCard: { flex: 1, backgroundColor: '#FFFFFF', borderRadius: 12, padding: 14, alignItems: 'center', gap: 6 },
  quickText: { color: '#94A3B8', fontSize: 11, fontWeight: '600' },

  // Chat
  chatHeader: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#FFFFFF' },
  chatTitle: { color: '#0F172A', fontSize: 14, fontWeight: '600' },
  chatLang: { color: '#6B7280', fontSize: 11 },
  ttsBtn: { padding: 8 },
  stopBtn: { padding: 8 },

  chatMessages: { flex: 1, marginTop: 8 },

  welcomeMsg: { alignItems: 'center', paddingVertical: 40 },
  welcomeTitle: { color: '#0F172A', fontSize: 18, fontWeight: '700', marginTop: 12 },
  welcomeSub: { color: '#94A3B8', fontSize: 13, marginTop: 6, textAlign: 'center', lineHeight: 20, paddingHorizontal: 16 },
  suggestionRow: { marginTop: 16, gap: 8, width: '100%', paddingHorizontal: 16 },
  sugChip: { backgroundColor: '#FFFFFF', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#334155' },
  sugText: { color: '#A78BFA', fontSize: 13, fontWeight: '500' },

  msgBubble: { flexDirection: 'row', marginBottom: 12, alignItems: 'flex-start' },
  userBubble: { justifyContent: 'flex-end' },
  aiBubble: { justifyContent: 'flex-start' },
  aiAvatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#1E1B4B', justifyContent: 'center', alignItems: 'center', marginRight: 8, marginTop: 2 },
  msgContent: { maxWidth: '80%', borderRadius: 14, padding: 12 },
  userContent: { backgroundColor: '#6366F1', borderBottomRightRadius: 4, marginLeft: 'auto' },
  aiContent: { backgroundColor: '#FFFFFF', borderBottomLeftRadius: 4, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center' },
  msgText: { color: '#475569', fontSize: 14, lineHeight: 20 },
  speakBtn: { padding: 6, marginLeft: 4, marginTop: 2 },

  // Input
  inputBar: { flexDirection: 'row', alignItems: 'flex-end', paddingVertical: 8, borderTopWidth: 1, borderTopColor: '#FFFFFF', gap: 8 },
  chatInput: { flex: 1, backgroundColor: '#FFFFFF', borderRadius: 12, borderWidth: 1, borderColor: '#334155', color: '#0F172A', paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, maxHeight: 100 },
  sendBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#6366F1', justifyContent: 'center', alignItems: 'center' },
});
