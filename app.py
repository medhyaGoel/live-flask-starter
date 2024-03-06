from flask import Flask, render_template
from flask_socketio import SocketIO
from dotenv import load_dotenv
import logging
from threading import Event
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveOptions,
    Microphone, LiveTranscriptionEvents,
)
import requests

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

# Set up client configuration
config = DeepgramClientOptions(
    verbose=logging.DEBUG,
    options={"keepalive": "true"}
)

#logging.basicConfig(filename='app.log')

# Initialize Deepgram client and connection
deepgram = DeepgramClient("", config)
dg_connection = deepgram.listen.live.v("1")

# Track transcription state
transcribing = False
transcription_event = Event()

def configure_deepgram():
    options = LiveOptions(
        smart_format=True,
        language="en-US",
        encoding="linear16",
        channels=1,
        sample_rate=16000,
        diarize=True,
    )
    dg_connection.start(options)

def start_microphone():
    microphone = Microphone(dg_connection.send)
    microphone.start()
    return microphone

# # Later, you can save the transcriptions to a file or concatenate them into a string
def save_transcriptions_to_file(file_path, transcriptions):
    with open(file_path, 'w') as file:
        for transcript in transcriptions:
            file.write(transcript + '\n')
#
# def save_transcriptions_to_file(file_path, data):
#     with open(file_path, 'w') as file:
#         for entry in data:
#             file.write(f"[Speaker:{entry['speaker']}] {entry['transcript']}\n")

def start_transcription_loop():
    try:
        global transcribing
        while transcribing:
            configure_deepgram()

            # Open a microphone stream
            microphone = start_microphone()

            transcriptions = []

            # def on_message(self, result, **kwargs):
            #     for word in result.channel.alternatives[0].words:
            #         speaker = word['speaker']
            #         transcript = word['word']
            #         transcriptions.append({"speaker": speaker, "transcript": transcript})
            #         socketio.emit('transcription_update', {'transcription': transcript})
            def on_message(self, result, **kwargs):
                transcript = result.channel.alternatives[0].transcript
                # print(result.channel)
                # print(result.channel.alternatives)
                # print(result.channel.alternatives[0])
                # print(result.channel.alternatives[0].transcript)
                # print(result.channel.alternatives[0].words)
                if len(transcript) > 0:
                    transcriptions.append(transcript)
                    socketio.emit('transcription_update', {'transcription': transcript})

            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

            # Wait for the transcription to finish
            transcription_event.wait()
            transcription_event.clear()

            # Finish the microphone and Deepgram connection
            microphone.finish()
            dg_connection.finish()
            logging.info("Transcription loop finished.")
            transcript = "\n".join(transcriptions)
            # print(f"This is the transcript I generated for you: {transcript}")
            ask_chat(transcript)
            # print(transcriptions)
            save_transcriptions_to_file('transcriptions.txt', transcriptions)

    except Exception as e:
        logging.error(f"Error: {e}")


def ask_chat(transcript):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer "
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user",
                      "content": f"""I'm a realtor. Your client just called me. You are my secretary. 
        Under the heading 'FOLLOW-UP ITEMS' list out what follow-up actions I should take after the call ends, on 
        behalf of my client, informed by the call transcript below. Examples of follow-up items include: 
        Property Research: If the client expressed interest in a specific property during the call, I would conduct 
        additional research on the property to gather more detailed information. This may include reviewing property 
        listings, assessing the property's condition, checking comparable sales data, and gathering any relevant 
        documents or disclosures. Follow-Up Communication: Shortly after the call, I would send a follow-up email or text message to the client to 
summarize our discussion, confirm any action items or appointments agreed upon, and express my availability to assist 
further. Schedule Property Viewings: If the client expressed interest in viewing one or more properties, I would work with them to schedule appointments for property viewings at their convenience. I would coordinate with the property owners or listing agents to arrange the visits.
Prepare Property Information Packets: For scheduled property viewings, I would prepare informational packets containing details about the properties, including photos, floor plans, property descriptions, and any relevant neighborhood information.
Review Market Trends: I would review current market trends, recent property sales data, and local market conditions to provide the client with insights into property values, pricing strategies, and market dynamics.
Follow-Up with Sellers: If the client expressed interest in selling their current property, I would follow up with them to discuss the selling process, market evaluation of their property, and steps to prepare their home for sale.
Update Client Records: I would update my client database or CRM system with the details of the conversation, including any specific property preferences, contact information, and scheduled appointments. 
Continue Client Relationship: I would maintain regular communication with the client to provide updates on new listings, market changes, and relevant information to support their real estate goals. Building a strong relationship with the client is essential for long-term success in real estate. Afterwards, write an email from me to my client containing a call summary and following up on items discussed during the call to remind them of how useful realtors are, under the heading 'EMAIL'. Do not include any other information besides 'FOLLOW-UP ITEMS', the follow-up items, 'EMAIL', and the email. This is the call transcript: {transcript}"""}],
        "temperature": 0.7
    }
    response = requests.post(url, headers=headers, json=data)
    with open('follow-ups.txt', "w") as file:
        file.write(response.json()["choices"][0]["message"]["content"])



def reconnect():
    try:
        logging.info("Reconnecting to Deepgram...")
        new_dg_connection = deepgram.listen.live.v("1")

        # Configure and start the new Deepgram connection
        configure_deepgram(new_dg_connection)

        logging.info("Reconnected to Deepgram successfully.")
        return new_dg_connection

    except Exception as e:
        logging.error(f"Reconnection failed: {e}")
        return None

def on_disconnect():
    logging.info("Client disconnected")
    global dg_connection
    if dg_connection:
        dg_connection.finish()
        dg_connection = None
        logging.info("Cleared listeners and set dg_connection to None")
    else:
        logging.info("No active dg_connection to disconnect from")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/unlocked_intel')
def new_analysis():
    followups = []
    email_text = []

    # Flag to indicate whether to start capturing lines
    capture_followups = False

    with open('follow-ups.txt', 'r') as file:
        for line in file:
            if "FOLLOW-UP ITEMS" in line:
                # Start capturing lines
                capture_followups = True
                continue
            elif "EMAIL" in line:
                # Stop capturing lines
                capture_followups = False
                continue

            if capture_followups:
                followups.append(line.rstrip('\n'))  # Remove newline character
            else:
                email_text.append(line.rstrip('\n'))  # Remove newline character

    # with open('follow-ups.txt', 'r') as file:
    #     file_content = file.read()
    #
    # # Find the starting and ending indices of the desired substring
    # start_index = file_content.find('FOLLOW-UP ITEMS:') + len('FOLLOW-UP ITEMS:')
    # end_index = file_content.find('EMAIL:')
    #
    # # Extract the substring between the start and end indices
    # followups = file_content[start_index:end_index]
    # start_index = file_content.find('EMAIL:') + len('EMAIL:')
    # # Print or process the extracted substring
    # email = file_content[start_index:]
    # print(email)
    # print(followups)


    return render_template('unlocked.html', action_items=followups, email=email_text)

@socketio.on('disconnect')
def handle_disconnect():
    socketio.start_background_task(target=on_disconnect)

@socketio.on('toggle_transcription')
def toggle_transcription(data):
    global transcribing
    action = data.get('action')

    if action == 'start' and not transcribing:
        # Start transcription
        transcribing = True
        socketio.start_background_task(target=start_transcription_loop)
    elif action == 'stop' and transcribing:
        # Stop transcription
        transcribing = False
        transcription_event.set()

if __name__ == '__main__':
    logging.info("Starting SocketIO server.")
    socketio.run(app, debug=True)
