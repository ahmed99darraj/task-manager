$(document).ready(function() {
    // تحديث حالة المهمة
    $('.status-select').change(function() {
        const taskId = $(this).data('task-id');
        const newStatus = $(this).val();
        
        $.ajax({
            url: `/update_status/${taskId}`,
            method: 'POST',
            data: { status: newStatus },
            success: function(response) {
                if (response.success) {
                    console.log('تم تحديث الحالة بنجاح');
                }
            },
            error: function() {
                alert('حدث خطأ أثناء تحديث الحالة');
            }
        });
    });

    // تنسيق التاريخ والوقت تلقائياً
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    
    const currentDateTime = `${year}-${month}-${day}T${hours}:${minutes}`;
    $('#due_date').attr('min', currentDateTime);

    // متغيرات الكاميرا
    let stream = null;
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const startButton = document.getElementById('startCamera');
    const takePhotoButton = document.getElementById('takePhoto');
    const photoPreview = document.getElementById('photoPreview');

    // فتح الكاميرا
    startButton.addEventListener('click', async function() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: true });
            video.srcObject = stream;
            video.style.display = 'block';
            takePhotoButton.style.display = 'block';
            startButton.style.display = 'none';
        } catch (err) {
            alert('لا يمكن الوصول إلى الكاميرا: ' + err.message);
        }
    });

    // التقاط صورة
    takePhotoButton.addEventListener('click', function() {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        
        // تحويل الصورة إلى blob
        canvas.toBlob(function(blob) {
            const formData = new FormData();
            formData.append('image', blob, 'camera_image.jpg');

            // رفع الصورة إلى الخادم
            $.ajax({
                url: '/upload_camera_image',
                method: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                success: function(response) {
                    if (response.success) {
                        // عرض معاينة الصورة
                        const img = document.createElement('img');
                        img.src = URL.createObjectURL(blob);
                        img.style.maxWidth = '200px';
                        photoPreview.innerHTML = '';
                        photoPreview.appendChild(img);
                        
                        // تخزين اسم الملف
                        $('#cameraImage').val(response.filename);
                    }
                },
                error: function() {
                    alert('حدث خطأ أثناء رفع الصورة');
                }
            });
        }, 'image/jpeg');

        // إغلاق الكاميرا
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            video.style.display = 'none';
            takePhotoButton.style.display = 'none';
            startButton.style.display = 'block';
        }
    });
});
