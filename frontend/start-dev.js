// frontend/start-dev.js
const { spawn } = require('child_process');
const fs = require('fs');

// Watch package.json for changes
fs.watch('package.json', (eventType, filename) => {
    if (eventType === 'change') {
        console.log('package.json changed, installing dependencies...');
        const install = spawn('npm', ['install'], { stdio: 'inherit' });
        
        install.on('error', (err) => {
            console.error('Failed to start npm install:', err);
        });
    }
});

// Start React development server
const npm = spawn('npm', ['start'], { stdio: 'inherit' });

npm.on('error', (err) => {
    console.error('Failed to start React server:', err);
});