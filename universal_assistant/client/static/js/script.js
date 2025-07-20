document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const modelSelector = document.getElementById('model');
    const micToggle = document.getElementById('mic-toggle');
    const speechToggle = document.getElementById('speech-toggle');
    const speechStatus = document.getElementById('speech-status');
    
    // Audio recording variables
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    
    // Speech synthesis variables
    let speechEnabled = false;
    
    // Function to find the last bot message
    function findLastBotMessage() {
        const botMessages = chatContainer.querySelectorAll('.message.bot');
        return botMessages.length > 0 ? botMessages[botMessages.length - 1] : null;
    }
    
    // Check if marked.js is loaded
    if (typeof marked === 'undefined') {
        console.error('Marked.js is not loaded properly');
        // Fallback to simple text display if marked is not available
        addMessageWithoutMarkdown('Markdown support is not available. The chat will still work but without formatting.', 'error');
    } else {
        // Configure marked.js for markdown parsing
        marked.setOptions({
            renderer: new marked.Renderer(),
            highlight: function(code, language) {
                // Check if hljs is available
                if (typeof hljs !== 'undefined') {
                    const validLanguage = hljs.getLanguage(language) ? language : 'plaintext';
                    return hljs.highlight(validLanguage, code).value;
                }
                return code; // Fallback if hljs is not available
            },
            pedantic: false,
            gfm: true,
            breaks: true,
            sanitize: false,
            smartypants: false,
            xhtml: false
        });
    }

    // Simple message function without markdown (fallback)
    function addMessageWithoutMarkdown(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        messageDiv.textContent = text;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return messageDiv;
    }

    function addMessage(text, sender, hasThinking = false, thinkingContent = null) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender); // sender is 'user', 'bot', 'error', or 'typing'
        
        try {
            // Apply Markdown parsing for bot messages only
            if (sender === 'bot' && text) {
                // Not using markdown for messages with thinking as they're handled specially
                if (!hasThinking) {
                    if (typeof marked !== 'undefined') {
                        messageDiv.innerHTML = marked.parse(text);
                        // Activate syntax highlighting for code blocks if hljs is available
                        if (typeof hljs !== 'undefined') {
                            messageDiv.querySelectorAll('pre code').forEach((block) => {
                                hljs.highlightBlock(block);
                            });
                        }
                    } else {
                        messageDiv.textContent = text;
                    }
                }
            }
            
            // For messages with thinking parts
            if (hasThinking && thinkingContent) {
                // Create a wrapper for the main message
                const messageText = document.createElement('div');
                if (typeof marked !== 'undefined') {
                    messageText.innerHTML = marked.parse(text);
                    // Activate syntax highlighting for code blocks
                    if (typeof hljs !== 'undefined') {
                        messageText.querySelectorAll('pre code').forEach((block) => {
                            hljs.highlightBlock(block);
                        });
                    }
                } else {
                    messageText.textContent = text;
                }
                messageDiv.appendChild(messageText);
                
                // Create toggle button
                const toggleBtn = document.createElement('div');
                toggleBtn.classList.add('thinking-toggle');
                toggleBtn.textContent = 'Show thinking process';
                toggleBtn.dataset.state = 'hidden';
                messageDiv.appendChild(toggleBtn);
                
                // Create thinking content container (hidden by default)
                const thinkingDiv = document.createElement('div');
                thinkingDiv.classList.add('thinking-content');
                thinkingDiv.textContent = thinkingContent;
                messageDiv.appendChild(thinkingDiv);
                
                // Add click event to toggle
                toggleBtn.addEventListener('click', () => {
                    if (toggleBtn.dataset.state === 'hidden') {
                        thinkingDiv.style.display = 'block';
                        toggleBtn.textContent = 'Hide thinking process';
                        toggleBtn.dataset.state = 'shown';
                    } else {
                        thinkingDiv.style.display = 'none';
                        toggleBtn.textContent = 'Show thinking process';
                        toggleBtn.dataset.state = 'hidden';
                    }
                });
            } else if (sender !== 'bot' || sender === 'error' || sender === 'typing') {
                // For user messages, error messages, and typing indicators - no markdown
                messageDiv.textContent = text;
            }
        } catch (error) {
            // If there's an error in markdown parsing, fall back to plain text
            console.error("Error parsing message:", error);
            messageDiv.textContent = text;
        }
        
        // Add speech synthesis for bot messages
        if (sender === 'bot' && speechEnabled && text.trim()) {
            console.log('Bot message detected, speech enabled:', speechEnabled);
            // Use a timeout to ensure the message is rendered first
            setTimeout(() => speakText(text), 100);
        }
        
        chatContainer.appendChild(messageDiv);
        // Scroll to the bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return messageDiv; // Return the element if needed (e.g., for removing typing indicator)
    }

    // Speech synthesis function
    async function speakText(text) {
        if (!speechEnabled || !text.trim()) {
            console.log('Speech synthesis skipped:', { speechEnabled, hasText: !!text.trim() });
            return;
        }
        
        console.log('Attempting speech synthesis for text:', text.substring(0, 50) + '...');
        
        try {
            const response = await fetch('http://localhost:7777/speak_json', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text.trim() })
            });
            
            console.log('TTS response status:', response.status);
            console.log('TTS response headers:', [...response.headers.entries()]);
            
            if (response.ok) {
                const audioBlob = await response.blob();
                console.log('Audio blob:', { 
                    size: audioBlob.size, 
                    type: audioBlob.type 
                });
                
                if (audioBlob.size > 0) {
                    // Ensure the blob has the correct MIME type
                    const correctedBlob = new Blob([audioBlob], { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(correctedBlob);
                    const audio = new Audio(audioUrl);
                    
                    // Set volume
                    audio.volume = 0.8;
                    
                    audio.onloadstart = () => console.log('Audio loading started');
                    audio.oncanplay = () => console.log('Audio ready to play');
                    audio.oncanplaythrough = () => console.log('Audio can play through');
                    audio.onplay = () => console.log('Audio playback started');
                    audio.onended = () => {
                        console.log('Audio playback ended');
                        URL.revokeObjectURL(audioUrl);
                    };
                    audio.onerror = (e) => {
                        console.error('Audio playback error:', e);
                        console.error('Audio error details:', audio.error);
                        URL.revokeObjectURL(audioUrl);
                    };
                    
                    // Try to play the audio
                    try {
                        await audio.play();
                        console.log('Audio play() called successfully');
                    } catch (playError) {
                        console.error('Audio play() failed:', playError);
                        // Try fallback endpoint
                        await speakTextFallback(text);
                    }
                } else {
                    console.error('Received empty audio blob');
                    await speakTextFallback(text);
                }
            } else {
                console.error('TTS request failed:', response.status);
                // Try fallback endpoint
                await speakTextFallback(text);
            }
        } catch (error) {
            console.error('TTS error:', error);
            // Try fallback endpoint
            await speakTextFallback(text);
        }
    }

    // Fallback TTS function using form data
    async function speakTextFallback(text) {
        try {
            const formData = new FormData();
            formData.append('text', text.trim());
            
            const response = await fetch('http://localhost:7777/speak', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                const audio = new Audio(audioUrl);
                
                audio.onended = () => {
                    URL.revokeObjectURL(audioUrl);
                };
                
                await audio.play();
            } else {
                console.error('TTS fallback also failed:', response.status);
            }
        } catch (error) {
            console.error('TTS fallback error:', error);
        }
    }

    async function sendMessage() {
        const prompt = userInput.value.trim();
        const selectedModel = modelSelector.value;

        if (!prompt) return; // Don't send empty messages

        addMessage(prompt, 'user');
        userInput.value = ''; // Clear input field
        sendButton.disabled = true; // Disable button while processing

        const typingIndicator = addMessage('I am thinking...', 'typing');

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ prompt: prompt, model: selectedModel }),
            });

            // Remove typing indicator (ensure it exists before trying to remove)
            if (typingIndicator && typingIndicator.parentNode === chatContainer) {
                chatContainer.removeChild(typingIndicator);
            }

            if (!response.ok) {
                // Try to parse error from backend JSON response
                let errorMsg = `HTTP error ${response.status}`;
                try {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        const errorData = await response.json();
                        if (errorData && errorData.error) {
                            errorMsg = `Error: ${errorData.error}`;
                        }
                    } else {
                        // If it's HTML or other content, get text for debugging
                        const errorText = await response.text();
                        console.error("Server returned HTML error:", errorText.substring(0, 200));
                        errorMsg = `HTTP error ${response.status}: Server returned HTML error page. Check server logs.`;
                    }
                } catch (parseError) {
                    console.error("Could not parse error response:", parseError);
                    // Fallback to status text if parsing fails
                    errorMsg = `HTTP error ${response.status}: ${response.statusText}`;
                }
                addMessage(errorMsg, 'error');
            } else {
                const data = await response.json();
                if (data.error) {
                    addMessage(`Error: ${data.error}`, 'error');
                } else if (data.response) {
                    // Check if response has thinking content
                    if (data.has_thinking && data.thinking) {
                        addMessage(data.response, 'bot', true, data.thinking);
                    } else {
                        addMessage(data.response, 'bot');
                    }
                } else {
                    addMessage("Received an empty response from the bot.", 'error');
                }
            }

        } catch (error) {
            // Ensure typing indicator is removed on network error
            if (typingIndicator && typingIndicator.parentNode === chatContainer) {
                chatContainer.removeChild(typingIndicator);
            }
            console.error('Fetch Error:', error);
            addMessage(`Network or fetch error: ${error.message}`, 'error');
        } finally {
            sendButton.disabled = false; // Re-enable button
            userInput.focus(); // Keep focus on input
        }
    }

    // Audio recording functions
    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                await transcribeAudio(audioBlob);
                
                // Stop all tracks to release microphone
                stream.getTracks().forEach(track => track.stop());
            };
            
            mediaRecorder.start();
            isRecording = true;
            
            // Update UI
            micToggle.classList.add('recording');
            micToggle.title = 'Click to stop recording';
            
        } catch (error) {
            console.error('Error accessing microphone:', error);
            addMessage('Error: Could not access microphone. Please check permissions.', 'error');
        }
    }
    
    function stopRecording() {
        if (mediaRecorder && isRecording) {
            mediaRecorder.stop();
            isRecording = false;
            
            // Update UI
            micToggle.classList.remove('recording');
            micToggle.title = 'Click to record audio';
        }
    }
    
    async function transcribeAudio(audioBlob) {
        const formData = new FormData();
        formData.append('recording', audioBlob, 'recording.wav');
        
        // Show transcription in progress
        const transcriptionIndicator = addMessage('Transcribing audio...', 'typing');
        
        try {
            const response = await fetch('http://localhost:7777/transcribe', {
                method: 'POST',
                body: formData
            });
            
            // Remove transcription indicator
            if (transcriptionIndicator && transcriptionIndicator.parentNode === chatContainer) {
                chatContainer.removeChild(transcriptionIndicator);
            }
            
            if (!response.ok) {
                throw new Error(`Transcription failed: ${response.status} ${response.statusText}`);
            }
            
            const data = await response.json();
            const transcription = data.response || data.message || '';
            
            if (transcription.trim()) {
                // Put transcribed text in input field
                userInput.value = transcription.trim();
                // Optionally auto-send the message
                // await sendMessage();
            } else {
                addMessage('No speech detected in the recording.', 'error');
            }
            
        } catch (error) {
            // Remove transcription indicator on error
            if (transcriptionIndicator && transcriptionIndicator.parentNode === chatContainer) {
                chatContainer.removeChild(transcriptionIndicator);
            }
            console.error('Transcription error:', error);
            addMessage(`Transcription error: ${error.message}`, 'error');
        }
    }

    sendButton.addEventListener('click', sendMessage);

    // Microphone toggle event listener
    micToggle.addEventListener('click', () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    userInput.addEventListener('keypress', (event) => {
        // Send message on Enter key press
        if (event.key === 'Enter') {
            event.preventDefault(); // Prevent default form submission/newline
            sendMessage();
        }
    });

    // Speech toggle event listener
    speechToggle.addEventListener('click', () => {
        speechEnabled = !speechEnabled;
        console.log('Speech toggle clicked, new state:', speechEnabled);
        speechStatus.textContent = `Speech: ${speechEnabled ? 'ON' : 'OFF'}`;
        speechToggle.classList.toggle('active', speechEnabled);
    });

    // Log a message to confirm script is running
    console.log('Chat interface initialized with audio recording and TTS functionality');
});
