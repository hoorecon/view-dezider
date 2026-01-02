import React, { useEffect, useState } from 'react';
import { SafeAreaView, StyleSheet, Text, TextInput, TouchableOpacity, View, FlatList } from 'react-native';

const apiBase = 'http://localhost:8080/api';

export default function App() {
  const [token, setToken] = useState('');
  const [projects, setProjects] = useState([]);
  const [projectName, setProjectName] = useState('');

  const fetchProjects = async () => {
    if (!token) return;
    const response = await fetch(`${apiBase}/projects`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await response.json();
    setProjects(data);
  };

  const createProject = async () => {
    if (!token || !projectName) return;
    await fetch(`${apiBase}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ name: projectName })
    });
    setProjectName('');
    fetchProjects();
  };

  useEffect(() => {
    fetchProjects();
  }, [token]);

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>View Dezider</Text>
      <TextInput
        style={styles.input}
        placeholder="Paste JWT token"
        value={token}
        onChangeText={setToken}
      />
      <View style={styles.card}>
        <Text style={styles.subtitle}>Create Project</Text>
        <TextInput
          style={styles.input}
          placeholder="Project name"
          value={projectName}
          onChangeText={setProjectName}
        />
        <TouchableOpacity style={styles.button} onPress={createProject}>
          <Text style={styles.buttonText}>Create</Text>
        </TouchableOpacity>
      </View>
      <View style={styles.card}>
        <Text style={styles.subtitle}>Projects</Text>
        <FlatList
          data={projects}
          keyExtractor={(item) => `${item.id}`}
          renderItem={({ item }) => (
            <Text style={styles.listItem}>{item.name}</Text>
          )}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f8fafc'
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 16
  },
  subtitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8
  },
  input: {
    backgroundColor: '#fff',
    borderColor: '#e2e8f0',
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12
  },
  card: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 16,
    marginBottom: 16,
    shadowColor: '#0f172a',
    shadowOpacity: 0.08,
    shadowRadius: 12
  },
  button: {
    backgroundColor: '#2563eb',
    padding: 12,
    borderRadius: 12,
    alignItems: 'center'
  },
  buttonText: {
    color: '#fff',
    fontWeight: '600'
  },
  listItem: {
    paddingVertical: 6,
    fontSize: 16
  }
});
