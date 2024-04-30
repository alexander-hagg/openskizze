document.addEventListener('DOMContentLoaded', function() {
    const columns = document.querySelectorAll('.resizable-column');

    columns.forEach(column => {
        // Create grip element and append it to each column
        const grip = document.createElement('div');
        grip.classList.add('grip');
        column.appendChild(grip);

        let startX, startWidth;

        grip.addEventListener('mousedown', function(e) {
            startX = e.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(column).width, 10);

            document.documentElement.addEventListener('mousemove', doDrag, false);
            document.documentElement.addEventListener('mouseup', stopDrag, false);
        });

        function doDrag(e) {
            column.style.width = (startWidth + e.clientX - startX) + 'px';
        }

        function stopDrag() {
            document.documentElement.removeEventListener('mousemove', doDrag, false); 
            document.documentElement.removeEventListener('mouseup', stopDrag, false);
        }
    });
});