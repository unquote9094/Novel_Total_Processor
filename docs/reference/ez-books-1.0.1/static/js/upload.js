// EZ-Books Upload Handler

document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    const fileInput = uploadForm.querySelector('input[type="file"]');
    const submitButton = uploadForm.querySelector('button[type="submit"]');
    const uploadStatus = document.getElementById('upload-status');

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const file = fileInput.files[0];
        if (!file) {
            showStatus('Please select an EPUB file', 'error');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.epub')) {
            showStatus('Please select a valid EPUB file', 'error');
            return;
        }

        await uploadFile(file);
    });

    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        // Disable form during upload
        submitButton.disabled = true;
        fileInput.disabled = true;
        showStatus('Uploading... Please wait', 'info');

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || `Upload failed with status ${response.status}`);
            }

            const result = await response.json();
            showStatus(`Successfully uploaded: ${result.title}`, 'success');

            // Clear the file input
            fileInput.value = '';

            // Refresh the gallery after a short delay
            setTimeout(() => {
                window.location.reload();
            }, 1500);

        } catch (error) {
            console.error('Upload error:', error);
            showStatus(`Upload failed: ${error.message}`, 'error');
        } finally {
            // Re-enable form
            submitButton.disabled = false;
            fileInput.disabled = false;
        }
    }

    function showStatus(message, type) {
        if (!uploadStatus) return;

        uploadStatus.textContent = message;
        uploadStatus.style.color = getStatusColor(type);
    }

    function getStatusColor(type) {
        switch (type) {
            case 'success':
                return '#2ecc71';
            case 'error':
                return '#e74c3c';
            case 'info':
                return '#3498db';
            default:
                return '#ecf0f1';
        }
    }

    // Handle delete buttons
    document.addEventListener('click', async (e) => {
        if (e.target.classList.contains('delete')) {
            const bookId = e.target.dataset.id;
            const bookCard = e.target.closest('.book-card');
            const bookTitle = bookCard.querySelector('h3').textContent;

            if (!confirm(`Are you sure you want to delete "${bookTitle}"?`)) {
                return;
            }

            try {
                const response = await fetch(`/api/books/${bookId}`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    throw new Error(`Delete failed with status ${response.status}`);
                }

                // Remove the book card with animation
                bookCard.style.opacity = '0';
                bookCard.style.transform = 'scale(0.8)';
                setTimeout(() => {
                    bookCard.remove();

                    // Check if gallery is empty
                    const gallery = document.getElementById('gallery');
                    if (gallery.children.length === 0) {
                        gallery.innerHTML = `
                            <div class="empty-state">
                                <h2>No books yet</h2>
                                <p>Upload your first EPUB to get started!</p>
                            </div>
                        `;
                    }
                }, 300);

            } catch (error) {
                console.error('Delete error:', error);
                alert(`Failed to delete book: ${error.message}`);
            }
        }
    });
});
