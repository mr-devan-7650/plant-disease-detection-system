"""
Plant Disease Detection System - Flask Backend
Real-time Plant Leaf Disease Detection Using Deep Learning
"""
import firebase_admin
from firebase_admin import credentials, db
from gradio_client import Client, handle_file
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import requests as resend_requests
from datetime import datetime

# ================= RESEND CONFIG =================
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
ADMIN_EMAIL    = "ugale.ganesh.d@gmail.com"

# Initialize Flask app
app = Flask(__name__)

# ================= FIREBASE SETUP =================
firebase_key = json.loads(os.environ.get("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key)

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://plant-disease-history-default-rtdb.asia-southeast1.firebasedatabase.app'
})

# Create uploads folder if not exists
os.makedirs("static/uploads", exist_ok=True)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {
    'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tiff', 'tif',
    'svg', 'ico', 'heic', 'heif', 'avif', 'jfif', 'pjpeg',
    'pjp', 'raw', 'arw', 'cr2', 'nrw', 'k25', 'dng', 'orf',
    'rw2', 'nef', 'srw', 'x3f'
}

# Hugging Face Space client
hf_client = Client("ganeshugale47/plant-leaf-disease-detector")

# Global variables
prediction_history = []

# =========================
# FULL DISEASE INFO - All 38 Classes
# Keys match exactly what model returns after normalize_disease_name()
# Format: "Plant   Disease name" (triple underscore becomes 3 spaces)
# =========================

DISEASE_INFO = {
    "Apple   Apple scab": {
        "description": "Apple scab is a fungal disease caused by Venturia inaequalis. It appears as dark, olive-green to brown spots on leaves and fruit surfaces, leading to premature leaf drop and reduced fruit quality.",
        "treatment": "Apply fungicides such as captan, myclobutanil, or mancozeb during early spring. Remove and destroy infected leaves and fruit. Prune trees to improve air circulation.",
        "prevention": "Plant scab-resistant apple varieties. Rake and remove fallen leaves in autumn. Apply protective fungicide sprays starting at green tip stage in spring."
    },
    "Apple   Black rot": {
        "description": "Black rot is caused by the fungus Botryosphaeria obtusa. It causes circular brown lesions on leaves with purple borders, rotting fruit with concentric rings, and cankers on branches.",
        "treatment": "Remove mummified fruits and infected branches. Apply copper-based fungicides or captan. Prune out all cankered wood at least 15cm below the visible infection.",
        "prevention": "Maintain good orchard sanitation. Remove dead wood and mummified fruit. Avoid wounding trees. Ensure proper tree nutrition to reduce susceptibility."
    },
    "Apple   Cedar apple rust": {
        "description": "Cedar apple rust is caused by Gymnosporangium juniperi-virginianae. Yellow-orange spots appear on upper leaf surfaces in spring, with tube-like structures on the undersides. It requires both apple and cedar/juniper trees to complete its life cycle.",
        "treatment": "Apply fungicides containing myclobutanil, mancozeb, or sulfur at 7-10 day intervals starting at pink bud stage. Continue through petal fall.",
        "prevention": "Remove nearby cedar or juniper trees if possible. Plant rust-resistant apple varieties. Apply preventive fungicide sprays in early spring."
    },
    "Apple   healthy": {
        "description": "The apple plant appears healthy with no visible signs of disease or pest damage. Leaves are green and vibrant.",
        "treatment": "No treatment needed. Continue regular maintenance and monitoring.",
        "prevention": "Maintain proper watering, fertilization, and pruning schedules. Monitor regularly for early signs of disease or pests."
    },
    "Blueberry   healthy": {
        "description": "The blueberry plant appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Maintain acidic soil pH (4.5-5.5), proper irrigation, and annual pruning. Monitor regularly for early signs of disease."
    },
    "Cherry (including sour)   Powdery mildew": {
        "description": "Powdery mildew on cherry is caused by Podosphaera clandestina. It appears as white powdery coating on young leaves, shoots, and fruit, causing leaf distortion, premature defoliation, and reduced fruit quality.",
        "treatment": "Apply sulfur-based fungicides, potassium bicarbonate, or myclobutanil at first sign of infection. Remove and destroy infected plant parts.",
        "prevention": "Plant resistant varieties. Ensure good air circulation by proper pruning. Avoid excessive nitrogen fertilization. Apply preventive sprays in spring."
    },
    "Cherry (including sour)   healthy": {
        "description": "The cherry plant appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Maintain proper pruning for air circulation, adequate water, and balanced fertilization. Monitor regularly for early signs of disease."
    },
    "Corn (maize)   Cercospora leaf spot Gray leaf spot": {
        "description": "Gray leaf spot is caused by Cercospora zeae-maydis. It produces rectangular, tan to gray lesions with parallel edges running between leaf veins. Severe infections can cause significant yield loss.",
        "treatment": "Apply fungicides containing azoxystrobin, propiconazole, or pyraclostrobin when disease first appears. Ensure good field drainage.",
        "prevention": "Plant resistant hybrids. Practice crop rotation with non-host crops for at least 2 years. Till crop residue to reduce inoculum. Avoid planting in fields with history of severe infection."
    },
    "Corn (maize)   Common rust": {
        "description": "Common rust is caused by Puccinia sorghi. It produces small, circular to elongated, golden-brown to dark brown pustules on both leaf surfaces. Heavy infection causes leaves to yellow and die prematurely.",
        "treatment": "Apply foliar fungicides such as azoxystrobin or propiconazole if infection is severe and occurs before silking. Economic treatment is rarely needed if resistant hybrids are planted.",
        "prevention": "Plant rust-resistant corn hybrids. Monitor fields regularly during the growing season. Early planting can help avoid peak rust pressure periods."
    },
    "Corn (maize)   Northern Leaf Blight": {
        "description": "Northern Leaf Blight is caused by Exserohilum turcicum. It produces long, cigar-shaped, grayish-green to tan lesions (2.5-15 cm) on leaves. Severe infection can cause significant yield reduction.",
        "treatment": "Apply fungicides containing propiconazole, azoxystrobin, or tebuconazole at early disease onset, especially before tasseling. Focus on protecting upper leaves.",
        "prevention": "Plant resistant hybrids. Practice crop rotation. Till or incorporate crop residue. Avoid fields with history of severe NLB infection."
    },
    "Corn (maize)   healthy": {
        "description": "The corn plant appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Practice crop rotation, use certified seeds, maintain soil health, and monitor regularly for early signs of disease or pests."
    },
    "Grape   Black rot": {
        "description": "Black rot of grape is caused by Guignardia bidwellii. It causes tan or brown circular lesions with dark borders on leaves, and infected berries shrivel into hard, black mummies.",
        "treatment": "Apply fungicides containing myclobutanil, mancozeb, or captan starting at budbreak and continuing through berry development. Remove and destroy mummified berries and infected canes.",
        "prevention": "Remove all mummified fruit and infected material during dormant pruning. Improve air circulation by proper training and pruning. Apply protective fungicides starting at budbreak."
    },
    "Grape   Esca (Black Measles)": {
        "description": "Esca (Black Measles) is a complex fungal disease caused by several wood-rotting fungi. It produces tiger-stripe patterns of yellow and brown on leaves, and dark spots on berry skin giving a measles-like appearance. It can cause sudden vine death (apoplexy).",
        "treatment": "There is no cure for infected vines. Remove and destroy severely infected vines. Protect pruning wounds with fungicide paste or sealant. Some trunk renewal techniques may help.",
        "prevention": "Make clean pruning cuts during dry weather. Treat pruning wounds immediately with wound protectants. Avoid large pruning cuts. Use healthy certified planting material."
    },
    "Grape   Leaf blight (Isariopsis Leaf Spot)": {
        "description": "Leaf blight (Isariopsis Leaf Spot) is caused by Pseudocercospora vitis. It produces dark brown, angular spots on leaves, often surrounded by yellow halos. Severe infection leads to early defoliation.",
        "treatment": "Apply copper-based fungicides or mancozeb at the first sign of symptoms. Ensure good coverage of leaf undersides. Repeat applications every 10-14 days during wet conditions.",
        "prevention": "Improve air circulation through canopy management. Remove and destroy fallen infected leaves. Apply preventive copper sprays during the growing season."
    },
    "Grape   healthy": {
        "description": "The grape vine appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Maintain proper canopy management, balanced nutrition, and regular monitoring for early signs of disease or pests."
    },
    "Orange   Haunglongbing (Citrus greening)": {
        "description": "Huanglongbing (HLB) or Citrus Greening is a devastating bacterial disease caused by Candidatus Liberibacter asiaticus, spread by the Asian citrus psyllid. Symptoms include blotchy mottling of leaves, lopsided bitter fruit, and tree decline. There is no cure.",
        "treatment": "There is no effective cure. Remove and destroy infected trees to prevent spread. Control the Asian citrus psyllid vector with insecticides. Nutritional sprays may temporarily improve tree health.",
        "prevention": "Use certified disease-free nursery stock. Control Asian citrus psyllid populations with systemic insecticides. Monitor trees regularly for psyllids and early symptoms. Quarantine new plants."
    },
    "Peach   Bacterial spot": {
        "description": "Bacterial spot on peach is caused by Xanthomonas arboricola pv. pruni. It causes water-soaked spots on leaves that turn brown and fall out giving a shot-hole appearance. It also causes sunken dark lesions on fruit.",
        "treatment": "Apply copper-based bactericides starting at budbreak and continue through the season at 7-14 day intervals. Avoid wounding trees. Remove severely infected fruit.",
        "prevention": "Plant resistant varieties. Apply copper sprays preventively. Avoid overhead irrigation. Maintain good tree vigor with balanced fertilization. Prune to improve air circulation."
    },
    "Peach   healthy": {
        "description": "The peach tree appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Maintain proper pruning, balanced nutrition, and adequate irrigation. Monitor regularly for early signs of disease or pests."
    },
    "Pepper, bell   Bacterial spot": {
        "description": "Bacterial spot on bell pepper is caused by Xanthomonas campestris pv. vesicatoria. It causes small, water-soaked spots on leaves that turn brown with yellow halos, and raised or sunken scabby spots on fruit.",
        "treatment": "Apply copper-based bactericides mixed with mancozeb at first sign of disease. Repeat every 5-7 days during wet conditions. Remove and destroy heavily infected plants.",
        "prevention": "Use certified disease-free seed. Plant resistant varieties. Avoid overhead irrigation. Practice 2-3 year crop rotation. Disinfect tools and equipment."
    },
    "Pepper, bell   healthy": {
        "description": "The bell pepper plant appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Practice crop rotation, use disease-free seeds, maintain proper spacing for air circulation, and monitor regularly."
    },
    "Potato   Early blight": {
        "description": "Early blight of potato is caused by Alternaria solani. It produces dark brown to black lesions with concentric rings (target board pattern) on older leaves first, causing yellowing and defoliation from the bottom of the plant upward.",
        "treatment": "Apply fungicides containing chlorothalonil, mancozeb, or azoxystrobin at first sign of disease. Repeat every 7-10 days. Destroy infected plant debris after harvest.",
        "prevention": "Use certified disease-free seed potatoes. Practice 3-4 year crop rotation. Maintain adequate plant nutrition, especially potassium. Apply mulch to prevent soil splash. Avoid overhead irrigation."
    },
    "Potato   Late blight": {
        "description": "Late blight is caused by Phytophthora infestans, the same pathogen that caused the Irish Potato Famine. It produces water-soaked, pale green to brown lesions on leaves with white fuzzy growth on undersides in humid conditions. It can destroy an entire crop rapidly.",
        "treatment": "Apply fungicides containing chlorothalonil, mancozeb, or metalaxyl immediately at first sign of disease. In severe cases, destroy infected plants to prevent spread. Do not store infected tubers.",
        "prevention": "Plant resistant varieties. Use certified disease-free seed. Apply preventive fungicides during cool, wet weather. Destroy volunteer potato plants. Ensure good field drainage. Avoid overhead irrigation."
    },
    "Potato   healthy": {
        "description": "The potato plant appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Use certified seed potatoes, practice crop rotation, maintain proper soil drainage, and monitor regularly for early signs of disease."
    },
    "Raspberry   healthy": {
        "description": "The raspberry plant appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Maintain proper pruning to remove old canes, ensure good drainage, and monitor regularly for early signs of disease or pests."
    },
    "Soybean   healthy": {
        "description": "The soybean plant appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Practice crop rotation, use certified disease-free seeds, maintain proper plant spacing, and monitor regularly."
    },
    "Squash   Powdery mildew": {
        "description": "Powdery mildew on squash is caused by Podosphaera xanthii. It appears as white, powdery fungal growth on leaf surfaces, stems, and sometimes fruit. Infected leaves turn yellow and die, reducing plant vigor and yield.",
        "treatment": "Apply potassium bicarbonate, sulfur-based fungicides, or neem oil at first sign of infection. Remove severely infected leaves. Apply fungicide to leaf undersides as well.",
        "prevention": "Plant resistant varieties. Ensure good air circulation with proper spacing. Avoid overhead watering. Apply preventive sprays during warm, dry weather when humidity is high."
    },
    "Strawberry   Leaf scorch": {
        "description": "Leaf scorch on strawberry is caused by Diplocarpon earlianum. It produces small, irregular dark purple spots on leaves that expand and coalesce, giving leaves a scorched appearance. Severe infection causes defoliation and reduced plant vigor.",
        "treatment": "Apply fungicides containing captan or myclobutanil at first sign of disease. Remove and destroy infected leaves. Avoid overhead irrigation.",
        "prevention": "Plant resistant varieties. Use certified disease-free plants. Improve air circulation by proper plant spacing. Remove old leaves in early spring before new growth begins."
    },
    "Strawberry   healthy": {
        "description": "The strawberry plant appears healthy with no visible signs of disease or pest damage.",
        "treatment": "No treatment needed. Continue regular care and monitoring.",
        "prevention": "Use certified disease-free plants, practice proper spacing for air circulation, avoid overhead irrigation, and remove old foliage regularly."
    },
    "Tomato   Bacterial spot": {
        "description": "Bacterial spot on tomato is caused by Xanthomonas campestris pv. vesicatoria. It produces small, water-soaked spots on leaves that turn dark brown with yellow halos. Fruit develops raised, scabby spots reducing marketability.",
        "treatment": "Apply copper-based bactericides combined with mancozeb at first sign of disease every 5-7 days during wet weather. Remove and destroy heavily infected plant material.",
        "prevention": "Use certified disease-free seed. Plant resistant varieties. Avoid overhead irrigation. Practice 2-year crop rotation. Disinfect garden tools. Avoid working in wet fields."
    },
    "Tomato   Early blight": {
        "description": "Early blight of tomato is caused by Alternaria solani. It produces dark brown concentric ring lesions (bull's-eye pattern) on older leaves, causing yellowing and defoliation from the bottom upward. It can also affect stems and fruit.",
        "treatment": "Apply fungicides containing chlorothalonil, mancozeb, or copper at first sign of symptoms. Repeat every 7-10 days. Remove infected lower leaves. Stake plants to improve air circulation.",
        "prevention": "Use resistant varieties. Practice 3-year crop rotation. Mulch around plants to prevent soil splash. Avoid overhead watering. Maintain adequate potassium levels in soil."
    },
    "Tomato   Late blight": {
        "description": "Late blight on tomato is caused by Phytophthora infestans. It produces large, greasy, dark brown water-soaked lesions on leaves and stems with white fuzzy growth on undersides. It can destroy plants within days under cool, wet conditions.",
        "treatment": "Apply fungicides containing chlorothalonil, mancozeb, or copper-based products immediately at first sign. In severe outbreaks, remove and destroy all infected plants to prevent spread.",
        "prevention": "Plant resistant varieties. Apply preventive fungicides during cool, wet weather. Avoid overhead irrigation. Destroy volunteer tomato plants. Ensure good air circulation."
    },
    "Tomato   Leaf Mold": {
        "description": "Leaf mold is caused by Passalora fulva (formerly Fulvia fulva). It causes pale green to yellow spots on upper leaf surfaces with olive-green to brown velvety fungal growth on undersides. It thrives in high humidity greenhouses.",
        "treatment": "Apply fungicides containing chlorothalonil, mancozeb, or copper at first sign of disease. Reduce humidity by improving ventilation. Remove and destroy infected leaves.",
        "prevention": "Maintain greenhouse humidity below 85%. Ensure good ventilation and air circulation. Plant resistant varieties. Avoid overhead irrigation. Remove plant debris promptly."
    },
    "Tomato   Septoria leaf spot": {
        "description": "Septoria leaf spot is caused by Septoria lycopersici. It produces small, circular spots with dark brown borders and light gray centers with tiny dark specks (pycnidia) on lower leaves, spreading upward causing severe defoliation.",
        "treatment": "Apply fungicides containing chlorothalonil, mancozeb, or copper at first sign of disease every 7-10 days. Remove and destroy infected lower leaves to slow spread.",
        "prevention": "Practice 3-year crop rotation. Mulch plants to prevent soil splash. Avoid overhead watering. Remove and destroy plant debris at end of season. Stake plants to improve air flow."
    },
    "Tomato   Spider mites Two-spotted spider mite": {
        "description": "Two-spotted spider mites (Tetranychus urticae) cause stippling (tiny yellow dots) on leaf surfaces, with fine webbing visible under leaves. Severe infestations cause leaves to turn bronze, yellow, and drop, significantly reducing yield.",
        "treatment": "Apply miticides such as abamectin or bifenazate. Insecticidal soap or neem oil can be effective for light infestations. Spray leaf undersides thoroughly. Repeat applications every 5-7 days.",
        "prevention": "Maintain adequate plant hydration as drought-stressed plants are more susceptible. Introduce natural predators like predatory mites. Avoid excessive nitrogen fertilization. Monitor plants regularly."
    },
    "Tomato   Target Spot": {
        "description": "Target spot on tomato is caused by Corynespora cassiicola. It produces brown lesions with concentric rings (target pattern) on leaves, and can also affect stems and fruit with similar ring patterns. It causes defoliation in severe cases.",
        "treatment": "Apply fungicides containing chlorothalonil, azoxystrobin, or mancozeb at first sign of disease. Remove infected plant material. Improve air circulation by pruning.",
        "prevention": "Plant resistant varieties. Ensure proper plant spacing for good air circulation. Avoid overhead irrigation. Practice crop rotation. Remove plant debris at end of season."
    },
    "Tomato   Tomato Yellow Leaf Curl Virus": {
        "description": "Tomato Yellow Leaf Curl Virus (TYLCV) is transmitted by the silverleaf whitefly (Bemisia tabaci). Infected plants show yellowing and upward curling of young leaves, severe stunting, and little to no fruit production.",
        "treatment": "There is no cure for virus-infected plants. Remove and destroy infected plants promptly to prevent spread. Control whitefly populations with insecticides (imidacloprid, thiamethoxam) or reflective mulches.",
        "prevention": "Plant TYLCV-resistant varieties. Control whitefly populations early using sticky yellow traps, insecticides, or neem oil. Use reflective mulches. Install insect screens in greenhouses. Remove weed hosts."
    },
    "Tomato   Tomato mosaic virus": {
        "description": "Tomato Mosaic Virus (ToMV) causes mottled light and dark green mosaic patterns on leaves, leaf distortion, stunted growth, and reduced fruit quality with internal browning. It spreads through contact with infected plants and tools.",
        "treatment": "There is no cure for virus-infected plants. Remove and destroy infected plants. Disinfect all tools and hands after handling plants. Avoid tobacco products near plants as they can be a source of virus.",
        "prevention": "Use certified virus-free seed. Plant resistant varieties. Disinfect tools with 10% bleach solution. Wash hands thoroughly before handling plants. Control aphid populations which can spread the virus."
    },
    "Tomato   healthy": {
        "description": "The tomato plant appears healthy with no visible signs of disease or pest damage. Leaves are green and vibrant.",
        "treatment": "No treatment needed. Continue regular maintenance and monitoring.",
        "prevention": "Practice crop rotation, maintain proper spacing, use disease-free seeds, ensure balanced fertilization, and monitor regularly for early signs of disease or pests."
    }
}

DEFAULT_DISEASE_INFO = {
    'description': 'Plant disease detected. Consult with an agricultural expert for detailed diagnosis.',
    'treatment': 'Remove affected leaves, maintain plant hygiene, and apply appropriate treatments based on the specific disease.',
    'prevention': 'Regular monitoring, proper spacing, adequate nutrition, and water management are key prevention strategies.'
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def normalize_disease_name(name):
    """
    Normalize disease name from HF API output to match DISEASE_INFO keys.
    Model returns: Apple___Apple_scab, Corn_(maize)___healthy, etc.
    Target format: Apple   Apple scab, Corn (maize)   healthy, etc.
    """
    # Step 1: Fix bracket underscores — _(text) → (text)
    import re
    name = re.sub(r'_\(', ' (', name)
    name = re.sub(r'\)_', ') ', name)

    # Step 2: Replace triple underscores with 3 spaces
    name = name.replace('___', '   ')

    # Step 3: Replace remaining single underscores with spaces
    name = name.replace('_', ' ')

    # Step 4: Clean up extra spaces
    name = re.sub(r'  +', lambda m: m.group(0) if len(m.group(0)) == 3 else ' ', name)

    # Step 5: Strip trailing/leading whitespace
    name = name.strip()

    # Step 6: Remove trailing spaces before closing bracket
    name = name.replace(' )', ')')

    return name


def get_disease_info(disease_name):
    """
    Try to find disease info, with fallback fuzzy matching.
    """
    # Direct lookup first
    if disease_name in DISEASE_INFO:
        return DISEASE_INFO[disease_name]

    # Try normalized name
    normalized = normalize_disease_name(disease_name)
    if normalized in DISEASE_INFO:
        return DISEASE_INFO[normalized]

    # Try case-insensitive match
    lower = normalized.lower()
    for key in DISEASE_INFO:
        if key.lower() == lower:
            return DISEASE_INFO[key]

    # Partial match fallback
    for key in DISEASE_INFO:
        if lower in key.lower() or key.lower() in lower:
            return DISEASE_INFO[key]

    return DEFAULT_DISEASE_INFO


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/predict', methods=['POST'])
def predict():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload JPG, PNG, or JPEG.'}), 400

        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"✅ File saved: {filepath}")

        # ===============================
        # HUGGING FACE API PREDICTION
        # ===============================
        try:
            result = hf_client.predict(
                img=handle_file(filepath),
                api_name="/predict_disease"
            )

            print("HF RESULT:", result)

            prediction_text = str(result)
            disease_name = prediction_text
            confidence = 95.0

            # Extract confidence if available
            if "Confidence:" in prediction_text:
                try:
                    confidence_part = prediction_text.split("Confidence:")[-1].replace("%", "").strip()
                    confidence = float(confidence_part)
                except:
                    confidence = 95.0

            # Extract disease name if available
            if "Prediction:" in prediction_text:
                disease_name = prediction_text.split("Prediction:")[-1].split("Confidence:")[0].strip()

        except Exception as hf_error:
            print("❌ Hugging Face API Error:", hf_error)
            return jsonify({
                'success': False,
                'error': 'Prediction failed. The AI model may be temporarily unavailable. Please try again.'
            }), 500

        # Normalize and get disease info
        normalized_name = normalize_disease_name(disease_name)
        disease_info = get_disease_info(disease_name)

        print(f"Disease: {disease_name} → Normalized: {normalized_name}")
        print(f"Info found: {'✅ Specific' if disease_info != DEFAULT_DISEASE_INFO else '⚠️ Default fallback'}")

        response = {
            'success': True,
            'disease': normalized_name,
            'confidence': round(confidence, 2),
            'top_predictions': [],
            'info': disease_info,
            'image_url': f'/static/uploads/{filename}',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        prediction_history.append(response)
        # ✅ SAVE TO FIREBASE
        db.reference('history').push(response)
        if len(prediction_history) > 50:
            prediction_history.pop(0)

        return jsonify(response)

    except Exception as e:
        print(f"❌ Error in predict route: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/history')
def history():
    try:
        ref = db.reference('history')
        data = ref.get()

        history_list = []
        if data:
            history_list = list(data.values())

        return jsonify({
            'success': True,
            'history': history_list[-10:]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/clear-history', methods=['POST'])
def clear_history():
    try:
        db.reference('history').delete()
        return jsonify({
            'success': True,
            'message': 'History cleared'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/history-by-date', methods=['POST'])
def history_by_date():
    try:
        selected_date = request.json.get('date')

        ref = db.reference('history')
        data = ref.get()

        filtered = []

        if data:
            for item in data.values():
                if item['timestamp'].startswith(selected_date):
                    filtered.append(item)

        return jsonify({
            'success': True,
            'history': filtered
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/contact')
def contact():
    return render_template('contact.html')


def send_admin_email(name, email, plant_name, disease_name, description, img_path=None):
    """Send contact request email to admin via Resend API."""
    try:
        if not RESEND_API_KEY:
            print("⚠️ RESEND_API_KEY not set — skipping email")
            return False

        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;background:#f0fdf4;padding:20px;">
        <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);">

            <div style="background:linear-gradient(135deg,#065f46,#10b981);padding:30px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:22px;">🌿 New Plant Addition Request</h1>
                <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:14px;">Plant Disease Detection System</p>
            </div>

            <div style="padding:30px;">
                <table style="width:100%;border-collapse:collapse;">
                    <tr>
                        <td style="padding:10px;background:#f9fafb;border-radius:8px;font-weight:bold;color:#065f46;width:140px;">👤 Name</td>
                        <td style="padding:10px;color:#1f2937;">{name}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px;font-weight:bold;color:#065f46;">📧 Email</td>
                        <td style="padding:10px;color:#1f2937;"><a href="mailto:{email}">{email}</a></td>
                    </tr>
                    <tr>
                        <td style="padding:10px;background:#f9fafb;border-radius:8px;font-weight:bold;color:#065f46;">🌱 Plant Name</td>
                        <td style="padding:10px;color:#1f2937;font-weight:600;">{plant_name}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px;font-weight:bold;color:#065f46;">🦠 Disease</td>
                        <td style="padding:10px;color:#1f2937;">{disease_name or 'Not specified'}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px;background:#f9fafb;border-radius:8px;font-weight:bold;color:#065f46;vertical-align:top;">📝 Description</td>
                        <td style="padding:10px;color:#1f2937;line-height:1.6;">{description}</td>
                    </tr>
                </table>

                <div style="margin-top:25px;padding:15px;background:#f0fdf4;border-radius:8px;border-left:4px solid #10b981;">
                    <p style="margin:0;color:#065f46;font-size:13px;">⚡ Reply directly to this email to contact the user at <strong>{email}</strong></p>
                </div>
            </div>

            <div style="padding:15px;background:#f9fafb;text-align:center;">
                <p style="margin:0;color:#9ca3af;font-size:12px;">Plant Disease Detection System | BE Computer Engineering Project 2026</p>
            </div>
        </div>
        </body></html>
        """

        payload = {
            "from": "Plant Disease App <onboarding@resend.dev>",
            "to": [ADMIN_EMAIL],
            "reply_to": email,
            "subject": f"🌿 New Plant Request: {plant_name} | Plant Disease Detection",
            "html": html_body
        }

        response = resend_requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10
        )

        if response.status_code == 200 or response.status_code == 201:
            print("✅ Admin email sent via Resend!")
            return True
        else:
            print(f"❌ Resend error: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False


@app.route('/submit-contact', methods=['POST'])
def submit_contact():
    try:
        data        = request.form
        name        = data.get('name', '')
        email       = data.get('email', '')
        plant_name  = data.get('plant_name', '')
        disease_name= data.get('disease_name', '')
        description = data.get('description', '')
        timestamp   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        img_path = None

        if 'image' in request.files:
            img_file = request.files['image']
            if img_file and img_file.filename:
                img_filename = secure_filename(img_file.filename)
                img_filename = f"contact_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{img_filename}"
                img_path = os.path.join(app.config['UPLOAD_FOLDER'], img_filename)
                img_file.save(img_path)

        contact_data = {
            'name': name,
            'email': email,
            'plant_name': plant_name,
            'disease_name': disease_name,
            'description': description,
            'timestamp': timestamp,
            'status': 'pending',
            'image_url': f'/static/uploads/{os.path.basename(img_path)}' if img_path else ''
        }
        db.reference('contact_requests').push(contact_data)

        # Email is best-effort — don't let it break the response
        email_sent = False
        try:
            email_sent = send_admin_email(name, email, plant_name, disease_name, description, img_path)
        except Exception as mail_err:
            print(f"⚠️ Email failed (non-critical): {mail_err}")

        return jsonify({
            'success': True,
            'message': 'Request submitted successfully!',
            'email_sent': email_sent
        })

    except Exception as e:
        print(f"❌ submit_contact error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/health')
def health():
    hf_reachable = False
    try:
        import requests as req
        resp = req.get(
            'https://ganeshugale47-plant-leaf-disease-detector.hf.space/',
            timeout=8
        )
        hf_reachable = resp.status_code in [200, 302, 401, 403]
    except Exception as e:
        print(f'HF health check failed: {e}')
        hf_reachable = False

    return jsonify({
        'status': 'healthy',
        'hf_connected': hf_reachable,
        'disease_classes': len(DISEASE_INFO)
    })


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    print("=" * 70)
    print("🌿 PLANT DISEASE DETECTION SYSTEM - STARTING")
    print(f"✅ Loaded {len(DISEASE_INFO)} disease classes with full info")
    print("🤖 Using Hugging Face API for prediction")
    print("=" * 70)

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
