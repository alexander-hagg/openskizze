document.addEventListener('DOMContentLoaded', () => {
    let isResizing = false;
    let startX, startWidth, nextStartWidth;
    let currentColumn, nextColumn, nextNextColumn;

    const columns = document.querySelectorAll('.column');
    const minWidth = 50;

    columns.forEach((column, index) => {
        if (index < columns.length - 1) {
            const resizer = document.createElement('div');
            resizer.className = 'resizer';
            column.appendChild(resizer);

            resizer.addEventListener('mousedown', (e) => {
                currentColumn = column;
                nextColumn = columns[index + 1];
                nextNextColumn = columns[index + 2] ? columns[index + 2] : null;
                isResizing = true;
                startX = e.clientX;
                startWidth = currentColumn.getBoundingClientRect().width;
                nextStartWidth = nextColumn.getBoundingClientRect().width;

                document.addEventListener('mousemove', onMouseMove);
                document.addEventListener('mouseup', onMouseUp);
            });
        }

        // Add click event to the title div to maximize the column
        const title = column.querySelector('.title');
        title.addEventListener('click', () => {
            maximizeColumn(column);
        });
    });

    function onMouseMove(e) {
        if (!isResizing) return;

        const dx = e.clientX - startX;
        let newCurrentWidth = startWidth + dx;
        let newNextWidth = nextStartWidth - dx;

        // Handle the case where the next column is being resized to its minimum width
        if (nextNextColumn && newNextWidth === 10) {
            const nextNextWidth = nextNextColumn.getBoundingClientRect().width - (newNextWidth - 10);
            nextNextColumn.style.width = `${nextNextWidth}px`;
        }

        currentColumn.style.width = `${newCurrentWidth}px`;
        nextColumn.style.width = `${newNextWidth}px`;
    }

    function onMouseUp() {
        if (!isResizing) return;

        isResizing = false;
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }

    function maximizeColumn(column) {
        // Calculate available width
        const containerWidth = document.querySelector('.container').getBoundingClientRect().width;
        const otherColumns = Array.from(columns).filter(col => col !== column);

        // Adjust other columns' width to minimum width
        otherColumns.forEach(col => col.style.width = `${minWidth}px`);

        // Set the clicked column's width to the remaining width
        const remainingWidth = containerWidth - (minWidth * otherColumns.length);
        column.style.width = `${remainingWidth}px`;
    }
});
