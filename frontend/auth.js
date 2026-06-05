const SUPABASE_URL = 'https://qpnbjhahxvjwncscyrde.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFwbmJqaGFoeHZqd25jc2N5cmRlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1ODk2NzksImV4cCI6MjA5NjE2NTY3OX0.qPc9G3suZMCuyBxtFLi7nSAZu5zmgS0LasGCD7WzBjw';

let supabase;
let currentUser = null;
let currentProfile = null;
let currentAccessToken = null;
let _authListeners = [];

function getAuthToken() {
    return currentAccessToken;
}

function initAuth() {
    if (!window.supabase) {
        console.error("Supabase script not loaded");
        return;
    }
    
    supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    
    // Check initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
        if (session) {
            currentUser = session.user;
            currentAccessToken = session.access_token;
            fetchProfile();
        } else {
            currentUser = null;
            currentProfile = null;
            currentAccessToken = null;
            notifyListeners();
        }
    });
    
    // Listen for auth changes
    supabase.auth.onAuthStateChange((event, session) => {
        if (session) {
            currentUser = session.user;
            currentAccessToken = session.access_token;
            fetchProfile();
        } else {
            currentUser = null;
            currentProfile = null;
            currentAccessToken = null;
            notifyListeners();
        }
    });
}

async function fetchProfile() {
    try {
        const token = (await supabase.auth.getSession()).data.session.access_token;
        const res = await fetch('/api/user/profile', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            currentProfile = await res.json();
        } else {
            // fallback if API not ready
            currentProfile = { role: 'free' };
        }
        notifyListeners();
    } catch (e) {
        console.error("Error fetching profile", e);
        notifyListeners();
    }
}

function notifyListeners() {
    for (const cb of _authListeners) {
        cb(currentUser, currentProfile);
    }
}

function onAuthStateChange(cb) {
    _authListeners.push(cb);
    if (supabase) cb(currentUser, currentProfile);
}

async function signInWithGoogle() {
    if (!supabase) initAuth();
    const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
            redirectTo: window.location.origin + '/'
        }
    });
    if (error) {
        alert("Login failed: " + error.message);
    }
}

async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    window.location.href = '/login.html';
}

async function getAuthHeaders() {
    if (!supabase) return {};
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
        return { 'Authorization': `Bearer ${session.access_token}` };
    }
    return {};
}

function getCurrentUser() {
    return currentUser;
}

function getProfile() {
    return currentProfile;
}

function isGuest() {
    return !currentUser;
}

function getRole() {
    return currentProfile ? currentProfile.role : 'guest';
}

function isAdmin() { return getRole() === 'admin'; }
function isPro() { return ['pro', 'scholar', 'admin'].includes(getRole()); }
function isScholar() { return ['scholar', 'admin'].includes(getRole()); }

window.addEventListener('DOMContentLoaded', initAuth);

async function signInWithEmail(email) {
    if (!supabase) initAuth();
    const { error } = await supabase.auth.signInWithOtp({
        email: email,
        options: {
            // set this to false if you do not want the user to be automatically signed up
            shouldCreateUser: true,
        },
    });
    return error ? error.message : null;
}

async function signInWithPhone(phone) {
    if (!supabase) initAuth();
    const { error } = await supabase.auth.signInWithOtp({
        phone: phone,
    });
    return error ? error.message : null;
}

async function verifyOTP(identifier, token, type) {
    if (!supabase) initAuth();
    const { data, error } = await supabase.auth.verifyOtp({
        [type]: identifier,
        token: token,
        type: type === 'email' ? 'email' : 'sms',
    });
    return error ? error.message : null;
}
