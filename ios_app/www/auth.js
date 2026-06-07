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
        console.error("Supabase script not loaded. Defaulting to logged-out state.");
        notifyListeners();
        return;
    }
    
    supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    
    // Check initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
        if (session) {
            currentUser = session.user;
            currentAccessToken = session.access_token;
            localStorage.removeItem('purangpt_guest');
            fetchProfile();
        } else {
            currentUser = null;
            currentProfile = null;
            currentAccessToken = null;
            notifyListeners();
            
            // Redirect to landing page if not logged in and not guest
            const onLoginPage = window.location.pathname.endsWith('login.html');
            const onLandingPage = window.location.pathname.endsWith('landing.html') || window.location.pathname.endsWith('/') || window.location.pathname.endsWith('index.html');
            const isGuest = localStorage.getItem('purangpt_guest') === 'true';
            if (!onLoginPage && !onLandingPage && !isGuest) {
                window.location.href = 'landing.html';
            }
        }
    });
    
    // Listen for auth changes
    supabase.auth.onAuthStateChange((event, session) => {
        if (session) {
            currentUser = session.user;
            currentAccessToken = session.access_token;
            localStorage.removeItem('purangpt_guest');
            fetchProfile();
        } else {
            currentUser = null;
            currentProfile = null;
            currentAccessToken = null;
            notifyListeners();
            
            // Redirect to landing page if not logged in and not guest
            const onLoginPage = window.location.pathname.endsWith('login.html');
            const onLandingPage = window.location.pathname.endsWith('landing.html') || window.location.pathname.endsWith('/') || window.location.pathname.endsWith('index.html');
            const isGuest = localStorage.getItem('purangpt_guest') === 'true';
            if (!onLoginPage && !onLandingPage && !isGuest) {
                window.location.href = 'landing.html';
            }
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
    // Always call immediately with current state (null if not initialized or failed)
    cb(currentUser, currentProfile);
}

async function signInWithGoogle() {
    if (!supabase) initAuth();
    if (!supabase) {
        alert("Authentication service is currently unavailable. Please check your network connection.");
        return;
    }
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

async function signInWithApple() {
    if (!supabase) initAuth();
    const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'apple',
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
    localStorage.removeItem('purangpt_guest');
    await supabase.auth.signOut();
    window.location.href = '/landing.html';
}

async function getAuthHeaders() {
    let headers = {};
    if (window.Capacitor && window.Capacitor.Plugins.Device) {
        try {
            const info = await window.Capacitor.Plugins.Device.getId();
            headers['X-Device-ID'] = info.identifier;
        } catch (e) {
            headers['X-Device-ID'] = localStorage.getItem('purangpt_fallback_id') || 'unknown';
        }
    } else {
        if (!localStorage.getItem('purangpt_fallback_id')) {
            localStorage.setItem('purangpt_fallback_id', 'web-' + Math.random().toString(36).substr(2, 9));
        }
        headers['X-Device-ID'] = localStorage.getItem('purangpt_fallback_id');
    }

    if (!supabase) return headers;
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
        headers['Authorization'] = `Bearer ${session.access_token}`;
    }
    return headers;
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
