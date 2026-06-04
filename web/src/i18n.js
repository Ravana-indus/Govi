// UI string bundles (mirror of backend i18n principle: no hard-coded text).
import { createContext, useContext } from "react";

export const STRINGS = {
  en: {
    appName: "FarmingOS",
    tagline: "Prices & plant health, in your language",
    farmer: "Farmer", pricePortal: "Price Portal", admin: "Admin", officer: "Officer",
    chooseLanguage: "Choose your language",
    phone: "Phone number", sendOtp: "Send code", otp: "Verification code",
    district: "District", consent: "I agree my data is used only to give me better advice.",
    finish: "Finish & start", next: "Next",
    askPlaceholder: "Ask a price, e.g. 'tomato price'",
    send: "Send", uploadLeaf: "Upload a leaf photo",
    onboardWelcome: "Welcome — let's get you set up in under 3 minutes.",
    chatTitle: "Ask FarmingOS",
    priceEntry: "Daily price entry", market: "Market", crop: "Crop",
    min: "Min (LKR/kg)", max: "Max (LKR/kg)", save: "Save price",
    bulkUpload: "Bulk CSV upload", coverage: "Today's coverage",
    login: "Log in", email: "Email", password: "Password",
    comingSoon: "Coming soon", phasedNote: "This console ships in a later phase.",
    privacy: "Privacy",
  },
  si: {
    appName: "FarmingOS",
    tagline: "මිල සහ පැළ සෞඛ්‍යය, ඔබේ භාෂාවෙන්",
    farmer: "ගොවියා", pricePortal: "මිල පෝට්ලය", admin: "පරිපාලක", officer: "නිලධාරී",
    chooseLanguage: "ඔබේ භාෂාව තෝරන්න",
    phone: "දුරකථන අංකය", sendOtp: "කේතය එවන්න", otp: "තහවුරු කේතය",
    district: "දිස්ත්‍රික්කය", consent: "මගේ දත්ත වඩා හොඳ උපදෙස් සඳහා පමණක් භාවිතා කරන බවට මම එකඟ වෙමි.",
    finish: "අවසන් කර අරඹන්න", next: "ඊළඟ",
    askPlaceholder: "මිලක් අහන්න, උදා: 'තක්කාලි මිල'",
    send: "යවන්න", uploadLeaf: "කොළ ඡායාරූපයක් උඩුගත කරන්න",
    onboardWelcome: "සාදරයෙන් පිළිගනිමු — මිනිත්තු 3කින් ලෑස්ති වෙමු.",
    chatTitle: "FarmingOS ගෙන් අහන්න",
    priceEntry: "දෛනික මිල ඇතුළත් කිරීම", market: "වෙළඳපොළ", crop: "භෝගය",
    min: "අවම (රු/කි.ග්‍රෑ)", max: "උපරිම (රු/කි.ග්‍රෑ)", save: "මිල සුරකින්න",
    bulkUpload: "තොග CSV උඩුගත කිරීම", coverage: "අද ආවරණය",
    login: "පිවිසෙන්න", email: "විද්‍යුත් තැපෑල", password: "මුරපදය",
    comingSoon: "ඉක්මනින්", phasedNote: "මෙම කොන්සෝලය පසු අදියරකදී.",
    privacy: "පෞද්ගලිකත්වය",
  },
  ta: {
    appName: "FarmingOS",
    tagline: "விலை & தாவர ஆரோக்கியம், உங்கள் மொழியில்",
    farmer: "விவசாயி", pricePortal: "விலை போர்ட்டல்", admin: "நிர்வாகி", officer: "அலுவலர்",
    chooseLanguage: "உங்கள் மொழியைத் தேர்வுசெய்க",
    phone: "தொலைபேசி எண்", sendOtp: "குறியீட்டை அனுப்பு", otp: "சரிபார்ப்புக் குறியீடு",
    district: "மாவட்டம்", consent: "சிறந்த ஆலோசனைக்காக மட்டுமே எனது தரவு பயன்படுத்தப்படுவதை ஏற்கிறேன்.",
    finish: "முடித்து தொடங்கு", next: "அடுத்து",
    askPlaceholder: "ஒரு விலையைக் கேளுங்கள், எ.கா: 'தக்காளி விலை'",
    send: "அனுப்பு", uploadLeaf: "இலை புகைப்படத்தை பதிவேற்று",
    onboardWelcome: "வரவேற்கிறோம் — 3 நிமிடங்களில் தயாராகுவோம்.",
    chatTitle: "FarmingOS இடம் கேளுங்கள்",
    priceEntry: "தினசரி விலை பதிவு", market: "சந்தை", crop: "பயிர்",
    min: "குறைந்த (ரூ/கிகி)", max: "அதிக (ரூ/கிகி)", save: "விலையை சேமி",
    bulkUpload: "மொத்த CSV பதிவேற்றம்", coverage: "இன்றைய கவரேஜ்",
    login: "உள்நுழை", email: "மின்னஞ்சல்", password: "கடவுச்சொல்",
    comingSoon: "விரைவில்", phasedNote: "இந்த கன்சோல் பிற்கட்டத்தில் வரும்.",
    privacy: "தனியுரிமை",
  },
};

export const LangContext = createContext({ lang: "si", setLang: () => {} });
export function useT() {
  const { lang } = useContext(LangContext);
  return (key) => (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.en[key] || key;
}
