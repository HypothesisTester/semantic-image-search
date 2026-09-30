import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

// Firebase web config. These values identify the project; they are not secrets.
// Access to data is controlled by Firebase Auth and the Firestore security rules
// (see firestore.rules at the repo root). Photos themselves are stored by the
// backend's indexer, not Firebase Storage.
const firebaseConfig = {
  apiKey: "AIzaSyBONGMY72a-f3lTwIb-M-KCGar4hUckzv8",
  authDomain: "semantic-image-search-666d0.firebaseapp.com",
  projectId: "semantic-image-search-666d0",
  storageBucket: "semantic-image-search-666d0.firebasestorage.app",
  messagingSenderId: "857606090031",
  appId: "1:857606090031:web:df1937ced4e0b74d0685da",
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export default app;
