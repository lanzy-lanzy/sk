document.addEventListener('DOMContentLoaded', function() {
    function openModal() {
        const modal = document.getElementById('budgetModal');
        modal.classList.remove('hidden');
        setTimeout(() => {
            modal.querySelector('div > div').classList.remove('scale-95', 'opacity-0');
        }, 10);
    }

    function closeModal() {
        const modal = document.getElementById('budgetModal');
        modal.querySelector('div > div').classList.add('scale-95', 'opacity-0');
        setTimeout(() => {
            modal.classList.add('hidden');
        }, 300);
    }

    // ... (include all other functions here)

    // Close modal when clicking outside
    window.onclick = function(event) {
        const modals = [
            document.getElementById('budgetModal'),
            document.getElementById('projectModal'),
            document.getElementById('newYearBudgetModal')
        ];

        modals.forEach(modal => {
            if (event.target == modal) {
                modal.querySelector('div > div').classList.add('scale-95', 'opacity-0');
                setTimeout(() => {
                    modal.classList.add('hidden');
                }, 300);
            }
        });
    };

    var messages = document.querySelectorAll('.message');
    messages.forEach(function(message) {
        setTimeout(function() {
            message.style.transition = 'opacity 1s';
            message.style.opacity = '0';
            setTimeout(function() {
                message.remove();
            }, 1000);
        }, 3500);
    });

    const bar = document.getElementById('budget-usage-bar');
    const percentage = document.getElementById('usage-percentage');
    const targetPercentage = parseFloat(bar.dataset.targetPercentage);
    let currentPercentage = 0;

    function updateBar() {
        if (currentPercentage < targetPercentage) {
            currentPercentage += 1;
            bar.style.width = currentPercentage + '%';
            percentage.textContent = currentPercentage.toFixed(2);

            // Set color based on percentage
            if (currentPercentage <= 33) {
                bar.style.backgroundColor = 'green';
            } else if (currentPercentage <= 66) {
                bar.style.backgroundColor = 'yellow';
            } else {
                bar.style.backgroundColor = 'red';
            }

            requestAnimationFrame(updateBar);
        }
    }

    updateBar();
});
