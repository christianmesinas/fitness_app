// Intro questions value under range field

document.addEventListener("DOMContentLoaded", function () {
  var sliders = document.querySelectorAll(".question-range");

  sliders.forEach(function (slider) {
    var outputId = slider.getAttribute("data-output");
    var output = document.getElementById(outputId);

    if (output) {
      // Zet initiële waarde
      output.textContent = slider.value;

      // Update bij verandering
      slider.addEventListener("input", function () {
        output.textContent = this.value;
      });
    }
  });
});
